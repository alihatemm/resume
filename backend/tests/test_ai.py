import json
import os
import sqlite3
import time
from typing import get_args

import httpx
import pytest
from google.genai import errors

from app import ai, config
from app.git_context import allowed_files, capture, sanitize

from .conftest import FAKE_GOOGLE_KEY

DOC_URL = "https://fastapi.tiangolo.com/tutorial/middleware/"


def good_output(**overrides):
    data = {
        "title": "Missing auth header in /me",
        "doing": "Tracing why the Authorization header disappears before the /me handler.",
        "problem": "request.headers has no authorization key, so /me raises KeyError.",
        "tried": ["Added header filtering in AuthMiddleware"],
        "errors": ["KeyError: 'authorization'"],
        "files": [
            {"path": "middleware.py", "reason": "Filters headers before the app sees them."},
            {"path": "main.py", "reason": "The /me handler that raises."},
        ],
        "next_step": "Remove the authorization filter in AuthMiddleware.__call__.",
        "next_step_detail": "Delete the list comprehension and rerun the request.",
        "links": [{"title": "FastAPI middleware docs", "url": DOC_URL}],
    }
    data.update(overrides)
    return json.dumps(data)


@pytest.fixture
def ctx(repo):
    """Changed middleware.py (untracked), unchanged main.py mentioned in terminal output."""
    (repo / "middleware.py").write_text("def strip(scope):\n    return [h for h in scope if h[0] != b'authorization']\n")
    git = capture(repo)
    note = "Auth header is missing in /me. Check middleware next."
    terminal = f'GEMINI_API_KEY={FAKE_GOOGLE_KEY}\n  File "{repo}/main.py", line 2\nKeyError: \'authorization\''
    terminal = sanitize(terminal)
    allowed = allowed_files(repo, git, [note, terminal])
    return git, note, terminal, "", [DOC_URL], allowed


@pytest.fixture
def fake_gemini(monkeypatch):
    """Replaces the network call. Set .response (str) or .error (Exception)."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(config, "GEMINI_MODEL", "primary-model")
    monkeypatch.setattr(config, "GEMINI_FALLBACK_MODEL", "fallback-model")

    class Fake:
        response = good_output()
        error = None
        calls = []

        def __call__(self, prompt, schema, model):
            self.calls.append((prompt, schema, model))
            if isinstance(self.error, list):  # sequence of outcomes per attempt
                outcome = self.error.pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
            if self.error:
                raise self.error
            return self.response

    fake = Fake()
    fake.calls = []
    fake.models = lambda: [c[2] for c in fake.calls]
    monkeypatch.setattr(ai, "_call_gemini", fake)
    return fake


# ---------- happy path ----------

def test_valid_output_maps_to_summary(ctx, fake_gemini):
    summary, status = ai.summarize(*ctx)

    assert status == "ready"
    assert summary.title == "Missing auth header in /me"
    assert summary.tried == ["Added header filtering in AuthMiddleware"]
    assert [f.path for f in summary.files] == ["middleware.py", "main.py"]
    assert all(f.line is None and f.abs_path is None for f in summary.files)
    assert summary.links[0].title == "FastAPI middleware docs"


def test_allowed_files_include_mentioned_tracked_file(ctx):
    allowed = dict(ctx[5])
    assert allowed == {"middleware.py": "??", "main.py": "mentioned"}


def test_schema_restricts_paths_to_allowlist(ctx, fake_gemini):
    ai.summarize(*ctx)
    _, schema, _ = fake_gemini.calls[0]
    path_type = schema.model_fields["files"].annotation.__args__[0].model_fields["path"].annotation
    assert set(get_args(path_type)) == {"middleware.py", "main.py"}


def test_prompt_is_sanitized_and_lists_allowed_files(ctx, fake_gemini):
    ai.summarize(*ctx)
    prompt, _, _ = fake_gemini.calls[0]
    assert FAKE_GOOGLE_KEY not in prompt
    assert "[REDACTED]" in prompt
    assert "<allowed_files>\nmiddleware.py (new, untracked)\nmain.py (unchanged, mentioned" in prompt


# ---------- hallucination defenses ----------

def test_invented_files_are_dropped(ctx, fake_gemini):
    fake_gemini.response = good_output(files=[
        {"path": "auth/jwt.py", "reason": "invented"},
        {"path": "./middleware.py", "reason": "normalized"},
        {"path": ".env", "reason": "secret file"},
        {"path": "middleware.py", "reason": "duplicate"},
    ])
    summary, status = ai.summarize(*ctx)
    assert status == "ready"
    assert [f.path for f in summary.files] == ["middleware.py"]


def test_invented_links_are_dropped_and_user_links_kept(ctx, fake_gemini):
    fake_gemini.response = good_output(links=[
        {"title": "Made up", "url": "https://example.com/invented-page"},
    ])
    summary, _ = ai.summarize(*ctx)
    assert [link.url for link in summary.links] == [DOC_URL]


def test_ai_output_is_sanitized(ctx, fake_gemini):
    fake_gemini.response = good_output(next_step=f"Rotate key {FAKE_GOOGLE_KEY} now.")
    summary, _ = ai.summarize(*ctx)
    assert FAKE_GOOGLE_KEY not in summary.model_dump_json()


# ---------- failures -> placeholder, never lost ----------

@pytest.mark.parametrize("bad", ["not json", "{}", json.dumps({"title": "only a title"}), ""])
def test_malformed_output_falls_back(ctx, fake_gemini, bad):
    fake_gemini.response = bad
    summary, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert summary.title == "Auth header is missing in /me. Check middleware next."  # note's first line
    assert summary.next_step == "Check middleware next."


RATE_LIMITED = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
UNAVAILABLE = errors.ServerError(503, {"error": {"code": 503, "message": "down", "status": "UNAVAILABLE"}})


@pytest.mark.parametrize("error", [
    errors.ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}}),
    errors.ClientError(403, {"error": {"code": 403, "message": "denied", "status": "PERMISSION_DENIED"}}),
    ai.EmptyResponseError("blocked"),
    RuntimeError("boom"),
])
def test_non_availability_errors_do_not_use_fallback(ctx, fake_gemini, error):
    fake_gemini.error = error
    _, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert fake_gemini.models() == ["primary-model"]


def test_malformed_primary_output_does_not_use_fallback(ctx, fake_gemini):
    fake_gemini.response = "not json"
    _, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert fake_gemini.models() == ["primary-model"]


@pytest.mark.parametrize("error", [RATE_LIMITED, UNAVAILABLE])
def test_availability_error_uses_fallback_model(ctx, fake_gemini, error):
    fake_gemini.error = [error, good_output()]
    summary, status = ai.summarize(*ctx)
    assert status == "ready"
    assert summary.title == "Missing auth header in /me"
    assert fake_gemini.models() == ["primary-model", "fallback-model"]


def test_both_models_unavailable_falls_back_to_placeholder(ctx, fake_gemini):
    fake_gemini.error = [UNAVAILABLE, RATE_LIMITED, good_output()]
    summary, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert summary.next_step == "Check middleware next."
    assert fake_gemini.models() == ["primary-model", "fallback-model"]  # no third attempt


def test_malformed_fallback_output_is_placeholder(ctx, fake_gemini):
    fake_gemini.error = [RATE_LIMITED, "not json"]
    _, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert fake_gemini.models() == ["primary-model", "fallback-model"]


def test_no_fallback_when_too_little_time_remains(ctx, fake_gemini, monkeypatch):
    monkeypatch.setattr(ai, "AI_DEADLINE_SECONDS", 5.0)  # less than FALLBACK_MIN_REMAINING_SECONDS
    fake_gemini.error = [UNAVAILABLE, good_output()]
    _, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert fake_gemini.models() == ["primary-model"]


@pytest.mark.parametrize("fallback", ["", "primary-model"])
def test_fallback_disabled_or_same_as_primary(ctx, fake_gemini, monkeypatch, fallback):
    monkeypatch.setattr(config, "GEMINI_FALLBACK_MODEL", fallback)
    fake_gemini.error = [UNAVAILABLE, good_output()]
    _, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert fake_gemini.models() == ["primary-model"]


def test_deadline_covers_primary_and_fallback(ctx, fake_gemini, monkeypatch):
    monkeypatch.setattr(ai, "AI_DEADLINE_SECONDS", 0.6)
    monkeypatch.setattr(ai, "FALLBACK_MIN_REMAINING_SECONDS", 0.1)
    calls = []

    def flaky_then_slow(prompt, schema, model):
        calls.append(model)
        if model == "primary-model":
            raise UNAVAILABLE
        time.sleep(3)
        return good_output()

    monkeypatch.setattr(ai, "_call_gemini", flaky_then_slow)
    started = time.monotonic()
    _, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert calls == ["primary-model", "fallback-model"]
    assert time.monotonic() - started < 1.2


def test_slow_gemini_hits_deadline_quickly(ctx, fake_gemini, monkeypatch):
    monkeypatch.setattr(ai, "AI_DEADLINE_SECONDS", 0.3)

    def slow(prompt, schema, model):
        time.sleep(2)
        return good_output()

    monkeypatch.setattr(ai, "_call_gemini", slow)
    started = time.monotonic()
    _, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert time.monotonic() - started < 1.0


def test_network_timeout_does_not_use_fallback(ctx, fake_gemini):
    fake_gemini.error = httpx.ReadTimeout("slow")
    _, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert fake_gemini.models() == ["primary-model"]


def test_missing_key_skips_call(ctx, fake_gemini, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    _, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert fake_gemini.calls == []


# ---------- through the API ----------

def test_api_saves_checkpoint_when_gemini_fails(client, repo, fake_gemini):
    (repo / "middleware.py").write_text("x = 1\n")
    fake_gemini.error = RuntimeError("Gemini down")
    res = client.post("/api/checkpoints", json={"repo_path": str(repo), "note": "Fix the header bug."})
    assert res.status_code == 201
    cp = res.json()
    assert cp["status"] == "ai_failed"
    assert cp["summary"]["next_step"] == "Fix the header bug."
    assert client.get(f"/api/checkpoints/{cp['id']}").json() == cp


def test_api_stores_ai_summary_without_secrets(client, repo, fake_gemini):
    (repo / "middleware.py").write_text("x = 1\n")
    res = client.post("/api/checkpoints", json={
        "repo_path": str(repo),
        "note": "Header bug",
        "terminal_text": f"export GEMINI_API_KEY={FAKE_GOOGLE_KEY}\nKeyError: 'authorization' in main.py",
        "links": [DOC_URL],
    })
    cp = res.json()
    assert cp["status"] == "ready"
    assert cp["summary"]["title"] == "Missing auth header in /me"
    assert FAKE_GOOGLE_KEY not in fake_gemini.calls[0][0]
    assert fake_gemini.models() == ["primary-model"]
    with sqlite3.connect(config.DB_PATH) as conn:
        assert FAKE_GOOGLE_KEY not in repr(conn.execute("SELECT * FROM checkpoints").fetchall())


# ---------- optional live test ----------

@pytest.mark.skipif(os.getenv("RESUME_LIVE_GEMINI") != "1", reason="set RESUME_LIVE_GEMINI=1 to call the real API")
def test_live_gemini(ctx, monkeypatch):
    from dotenv import dotenv_values

    monkeypatch.setattr(config, "GEMINI_API_KEY", dotenv_values(config.REPO_ROOT / ".env").get("GEMINI_API_KEY", ""))
    summary, status = ai.summarize(*ctx)
    assert status == "ready"
    assert {f.path for f in summary.files} <= {"middleware.py", "main.py"}


def test_logs_only_model_and_error_type(ctx, fake_gemini, caplog):
    caplog.set_level("INFO", logger="resume.ai")
    fake_gemini.error = [UNAVAILABLE, RATE_LIMITED]
    ai.summarize(*ctx)
    logs = caplog.text
    assert "primary-model" in logs and "fallback-model" in logs
    assert "ServerError 503" in logs and "ClientError 429" in logs
    assert "Auth header is missing" not in logs  # note text
    assert "KeyError" not in logs  # terminal text
    assert FAKE_GOOGLE_KEY not in logs and "test-key" not in logs


def test_both_models_get_low_thinking_config(monkeypatch):
    seen = []

    class FakeModels:
        def generate_content(self, model, contents, config):
            seen.append((model, config.thinking_config.thinking_level))
            return type("R", (), {"text": good_output()})()

    monkeypatch.setattr(ai, "_get_client", lambda: type("C", (), {"models": FakeModels()})())
    monkeypatch.setattr(config, "GEMINI_MODEL", "primary-model")
    ai._call_gemini("prompt", ai.AISummary, "primary-model")
    ai._call_gemini("prompt", ai.AISummary, "fallback-model")
    assert seen == [("primary-model", ai.types.ThinkingLevel.LOW), ("fallback-model", ai.types.ThinkingLevel.LOW)]


def test_fallback_rejecting_thinking_config_goes_straight_to_placeholder(ctx, fake_gemini):
    unsupported = errors.ClientError(400, {"error": {"code": 400, "message": "thinking_level not supported", "status": "INVALID_ARGUMENT"}})
    fake_gemini.error = [UNAVAILABLE, unsupported, good_output()]
    summary, status = ai.summarize(*ctx)
    assert status == "ai_failed"
    assert summary.next_step == "Check middleware next."  # M1 placeholder
    assert fake_gemini.models() == ["primary-model", "fallback-model"]  # no third attempt


def test_path_matching_exact_wins_and_prefix_strip_is_guarded(ctx, fake_gemini):
    # "a/main.py" is a real repo path; "middleware.py" is only reachable via a diff-style prefix.
    allowed = [("a/main.py", "M"), ("middleware.py", "M")]
    fake_gemini.response = good_output(files=[
        {"path": "a/main.py", "reason": "exact match, must not become main.py"},
        {"path": "b/middleware.py", "reason": "diff prefix, stripped because middleware.py is allowed"},
        {"path": "a/ghost.py", "reason": "stripped result not allowed -> dropped"},
        {"path": "b/a/main.py", "reason": "prefix strip yields allowed a/main.py -> duplicate, dropped"},
    ])
    summary, status = ai.summarize(*ctx[:5], allowed)
    assert status == "ready"
    assert [f.path for f in summary.files] == ["a/main.py", "middleware.py"]


def test_main_py_is_not_rewritten_when_only_a_main_py_is_allowed(ctx, fake_gemini):
    fake_gemini.response = good_output(files=[{"path": "main.py", "reason": "not allowed"}])
    summary, _ = ai.summarize(*ctx[:5], [("a/main.py", "M")])
    # The invented "main.py" is dropped; the placeholder's allowed file is used instead.
    assert [f.path for f in summary.files] == ["a/main.py"]
    assert summary.files[0].reason == "Modified"


def test_zero_allowed_files_yields_no_files(ctx, fake_gemini):
    fake_gemini.response = good_output(files=[{"path": "invented/app.py", "reason": "made up"}])
    summary, status = ai.summarize(*ctx[:5], [])
    assert status == "ready"
    assert summary.files == []
    _, schema, _ = fake_gemini.calls[0]
    assert schema is ai.AISummary  # no enum possible, server-side filter still applies


def test_system_instruction_declares_tags_as_resume_only():
    text = ai.prompts.SYSTEM_INSTRUCTION
    assert "supplied only by Resume" in text
    assert "literal captured data" in text
