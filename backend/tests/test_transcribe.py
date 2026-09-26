import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest
from google.genai import errors

from app import ai, config, transcribe

from .conftest import FAKE_GOOGLE_KEY

PAD = b"\0" * 2048
WEBM = b"\x1a\x45\xdf\xa3" + PAD  # Chrome MediaRecorder container
OGG = b"OggS" + PAD
MP4 = b"\0\0\0\x20ftypM4A " + PAD
WAV = b"RIFF\0\0\0\0WAVE" + PAD
MP3 = b"ID3" + PAD

SPOKEN = "I'm debugging the auth middleware. The test says the authorization header is missing."
UNAVAILABLE = errors.ServerError(503, {"error": {"code": 503, "message": "down", "status": "UNAVAILABLE"}})
RATE_LIMITED = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})


@pytest.fixture
def fake_audio_gemini(monkeypatch):
    """Replaces the network call. Set .response (str), .error (Exception) or .outcomes (list)."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(config, "GEMINI_MODEL", "primary-model")
    monkeypatch.setattr(config, "GEMINI_FALLBACK_MODEL", "fallback-model")

    class Fake:
        response = json.dumps({"transcript": SPOKEN})
        error = None
        outcomes = None

        def __init__(self):
            self.calls = []

        def __call__(self, data, mime, model):
            self.calls.append((mime, model, len(data)))
            if self.outcomes:
                outcome = self.outcomes.pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
            if self.error:
                raise self.error
            return self.response

        def models(self):
            return [c[1] for c in self.calls]

    fake = Fake()
    monkeypatch.setattr(transcribe, "_call_gemini_audio", fake)
    return fake


def post(client, data, content_type="audio/webm;codecs=opus"):
    headers = {"Content-Type": content_type} if content_type is not None else {}
    return client.post("/api/transcribe", content=data, headers=headers)


# ---------- happy path ----------

def test_chrome_webm_opus_is_transcribed(client, fake_audio_gemini):
    res = post(client, WEBM)
    assert res.status_code == 200
    assert res.json() == {"transcript": SPOKEN}
    assert fake_audio_gemini.calls == [("audio/webm", "primary-model", len(WEBM))]


@pytest.mark.parametrize(("content_type", "data", "gemini_mime"), [
    ("audio/webm", WEBM, "audio/webm"),
    ("audio/ogg;codecs=opus", OGG, "audio/ogg"),
    ("audio/mp4", MP4, "audio/m4a"),
    ("audio/x-m4a", MP4, "audio/m4a"),
    ("audio/mpeg", MP3, "audio/mp3"),
    ("audio/wav", WAV, "audio/wav"),
    ("AUDIO/WEBM; codecs=opus", WEBM, "audio/webm"),
])
def test_accepted_formats_are_mapped_for_gemini(client, fake_audio_gemini, content_type, data, gemini_mime):
    assert post(client, data, content_type).status_code == 200
    assert fake_audio_gemini.calls[0][0] == gemini_mime


def test_transcript_is_trimmed_sanitized_and_capped(client, fake_audio_gemini):
    long = f"  my key is {FAKE_GOOGLE_KEY} " + "word " * 2000
    fake_audio_gemini.response = json.dumps({"transcript": long})
    text = post(client, WEBM).json()["transcript"]
    assert FAKE_GOOGLE_KEY not in text and "[REDACTED]" in text
    assert text.startswith("my key is")
    assert len(text) == transcribe.MAX_TRANSCRIPT_CHARS


# ---------- input validation (no Gemini call) ----------

@pytest.mark.parametrize("data", [b"", b"\x1a\x45\xdf\xa3" + b"\0" * 995])
def test_empty_or_too_short_is_400(client, fake_audio_gemini, data):
    res = post(client, data)
    assert res.status_code == 400
    assert res.json()["detail"] == transcribe.EMPTY
    assert fake_audio_gemini.calls == []


def test_too_large_is_413(client, fake_audio_gemini):
    res = post(client, b"\x1a\x45\xdf\xa3" + b"\0" * transcribe.MAX_AUDIO_BYTES)
    assert res.status_code == 413
    assert res.json()["detail"] == transcribe.TOO_LARGE
    assert fake_audio_gemini.calls == []


def test_too_large_without_content_length_is_413(client, fake_audio_gemini):
    # Chunked upload: no Content-Length header, so the streaming cap must catch it.
    chunk = b"\0" * (1024 * 1024)
    body = iter([b"\x1a\x45\xdf\xa3"] + [chunk] * 6)
    res = client.post("/api/transcribe", content=body, headers={"Content-Type": "audio/webm"})
    assert res.status_code == 413
    assert fake_audio_gemini.calls == []


@pytest.mark.parametrize(("content_type", "data"), [
    ("text/plain", WEBM),
    ("video/mp4", MP4),
    ("audio/flac", b"fLaC" + PAD),
    ("audio/webm", OGG),        # declared type doesn't match the bytes
    ("audio/mp4", WEBM),
    ("audio/webm", b"<html>" + PAD),
])
def test_unsupported_or_mismatched_is_415(client, fake_audio_gemini, content_type, data):
    res = post(client, data, content_type)
    assert res.status_code == 415
    assert res.json()["detail"].startswith("Unsupported audio format")
    assert fake_audio_gemini.calls == []


def test_missing_content_type_is_415(client, fake_audio_gemini):
    res = client.post("/api/transcribe", content=WEBM)
    assert res.status_code == 415
    assert "missing Content-Type" in res.json()["detail"] or "application/octet-stream" in res.json()["detail"]


def test_missing_api_key_is_503_without_call(client, fake_audio_gemini, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    res = post(client, WEBM)
    assert res.status_code == 503
    assert res.json()["detail"] == transcribe.NO_KEY
    assert fake_audio_gemini.calls == []


# ---------- Gemini outcomes ----------

@pytest.mark.parametrize("transcript", ["", "   \n "])
def test_no_speech_is_422(client, fake_audio_gemini, transcript):
    fake_audio_gemini.response = json.dumps({"transcript": transcript})
    res = post(client, WEBM)
    assert res.status_code == 422
    assert res.json()["detail"] == transcribe.NO_SPEECH


@pytest.mark.parametrize("bad", ["not json", "{}", json.dumps({"text": "wrong field"})])
def test_malformed_output_is_503(client, fake_audio_gemini, bad):
    fake_audio_gemini.response = bad
    res = post(client, WEBM)
    assert res.status_code == 503
    assert res.json()["detail"] == transcribe.UNAVAILABLE
    assert fake_audio_gemini.models() == ["primary-model"]


@pytest.mark.parametrize("error", [
    errors.ClientError(400, {"error": {"code": 400, "message": "bad audio", "status": "INVALID_ARGUMENT"}}),
    errors.ClientError(403, {"error": {"code": 403, "message": "denied", "status": "PERMISSION_DENIED"}}),
    ai.EmptyResponseError("blocked"),
    RuntimeError("boom"),
])
def test_non_retriable_errors_are_503_without_fallback(client, fake_audio_gemini, error):
    fake_audio_gemini.error = error
    res = post(client, WEBM)
    assert res.status_code == 503
    assert fake_audio_gemini.models() == ["primary-model"]


@pytest.mark.parametrize("error", [UNAVAILABLE, RATE_LIMITED])
def test_availability_errors_use_fallback(client, fake_audio_gemini, error):
    fake_audio_gemini.outcomes = [error, json.dumps({"transcript": SPOKEN})]
    res = post(client, WEBM)
    assert res.status_code == 200
    assert fake_audio_gemini.models() == ["primary-model", "fallback-model"]


def test_both_models_unavailable_is_503(client, fake_audio_gemini):
    fake_audio_gemini.outcomes = [UNAVAILABLE, RATE_LIMITED, json.dumps({"transcript": SPOKEN})]
    assert post(client, WEBM).status_code == 503
    assert fake_audio_gemini.models() == ["primary-model", "fallback-model"]


def test_slow_primary_is_capped_and_fallback_runs(client, fake_audio_gemini, monkeypatch):
    monkeypatch.setattr(ai, "AI_DEADLINE_SECONDS", 1.5)
    monkeypatch.setattr(ai, "PRIMARY_ATTEMPT_SECONDS", 0.8)
    monkeypatch.setattr(ai, "FALLBACK_MIN_REMAINING_SECONDS", 0.6)
    calls = []

    def slow_primary(data, mime, model):
        calls.append(model)
        if model == "primary-model":
            time.sleep(1.1)
            raise UNAVAILABLE
        return json.dumps({"transcript": SPOKEN})

    monkeypatch.setattr(transcribe, "_call_gemini_audio", slow_primary)
    started = time.monotonic()
    res = post(client, WEBM)
    assert res.status_code == 200
    assert calls == ["primary-model", "fallback-model"]
    assert time.monotonic() - started < 1.5


def test_both_slow_hits_deadline(client, fake_audio_gemini, monkeypatch):
    monkeypatch.setattr(ai, "AI_DEADLINE_SECONDS", 0.6)
    monkeypatch.setattr(ai, "PRIMARY_ATTEMPT_SECONDS", 0.3)
    monkeypatch.setattr(ai, "FALLBACK_MIN_REMAINING_SECONDS", 0.1)

    def slow(data, mime, model):
        time.sleep(3)
        return json.dumps({"transcript": SPOKEN})

    monkeypatch.setattr(transcribe, "_call_gemini_audio", slow)
    started = time.monotonic()
    assert post(client, WEBM).status_code == 503
    assert time.monotonic() - started < 1.0


# ---------- side effects ----------

def test_never_touches_the_database(client, repo, fake_audio_gemini):
    client.post("/api/checkpoints", json={"repo_path": str(repo), "note": "existing"})
    with sqlite3.connect(config.DB_PATH) as conn:
        before = conn.execute("SELECT * FROM checkpoints").fetchall()

    post(client, WEBM)                          # success
    fake_audio_gemini.error = RuntimeError("x")
    post(client, WEBM)                          # AI failure
    post(client, b"")                           # validation failure

    with sqlite3.connect(config.DB_PATH) as conn:
        assert conn.execute("SELECT * FROM checkpoints").fetchall() == before
    assert len(client.get("/api/checkpoints").json()) == 1


def test_logs_contain_no_transcript_or_key(client, fake_audio_gemini, caplog):
    caplog.set_level("INFO")
    fake_audio_gemini.response = json.dumps({"transcript": f"{SPOKEN} {FAKE_GOOGLE_KEY}"})
    post(client, WEBM)
    fake_audio_gemini.outcomes = [UNAVAILABLE, RuntimeError("down")]
    post(client, WEBM)
    logs = caplog.text
    assert "primary-model" in logs and "audio/webm" in logs
    assert "auth middleware" not in logs and FAKE_GOOGLE_KEY not in logs and "test-key" not in logs


def test_summarization_path_is_untouched():
    # Transcription reuses ai.py helpers but must not replace any of them.
    assert ai._call_gemini.__module__ == "app.ai"
    assert ai._generate_with_deadline.__module__ == "app.ai"


# ---------- optional live test (one real Gemini call) ----------

@pytest.mark.skipif(os.getenv("RESUME_LIVE_GEMINI") != "1", reason="set RESUME_LIVE_GEMINI=1 to call the real API")
@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("say") or not shutil.which("afconvert"),
                    reason="needs macOS say/afconvert to synthesize real audio")
def test_live_gemini_transcribes_real_m4a(tmp_path, monkeypatch):
    from dotenv import dotenv_values

    aiff, m4a = tmp_path / "note.aiff", tmp_path / "note.m4a"
    subprocess.run(["say", "-o", str(aiff), SPOKEN], check=True)
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(aiff), str(m4a)], check=True)
    data = m4a.read_bytes()
    assert data[4:8] == b"ftyp"

    monkeypatch.setattr(config, "GEMINI_API_KEY", dotenv_values(config.REPO_ROOT / ".env").get("GEMINI_API_KEY", ""))
    text = transcribe.transcribe_audio(data, "audio/mp4").lower()
    assert "middleware" in text and "authorization" in text
