"""Turns captured context into a structured Summary using Gemini.

summarize() never raises: if Gemini is unavailable, slow, or returns bad data,
it returns a deterministic placeholder summary with status "ai_failed" so the
user's checkpoint is still saved.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Literal

import httpx
from google import genai
from google.genai import errors, types
from pydantic import Field, create_model

from . import config, prompts
from .git_context import sanitize
from .schemas import AIFile, AISummary, FileRef, GitContext, Link, Summary

log = logging.getLogger("resume.ai")

# Latency budget: the whole AI step (primary + optional fallback) must finish within this.
AI_DEADLINE_SECONDS = 15.0
# Only try the fallback model if at least this much of the budget is left.
FALLBACK_MIN_REMAINING_SECONDS = 6.0

MAX_FILES = 4
MAX_LIST_ITEMS = 6
_URL = re.compile(r"https?://[^\s<>\"'`)\]]+")

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gemini")
_client: genai.Client | None = None
_client_key = ""


class EmptyResponseError(Exception):
    pass


def summarize(
    git: GitContext,
    note: str,
    terminal_text: str,
    transcript: str,
    links: list[str],
    allowed: list[tuple[str, str]],
) -> tuple[Summary, str]:
    """Returns (summary, status). All inputs must already be sanitized."""
    fallback = _fallback_summary(git, note, terminal_text, transcript, links, allowed)
    if not config.GEMINI_API_KEY:
        log.info("GEMINI_API_KEY not set; using placeholder summary.")
        return fallback, "ai_failed"

    prompt = prompts.build_prompt(git, note, terminal_text, transcript, links, allowed)
    schema = _response_model([path for path, _ in allowed])
    started = time.monotonic()
    try:
        raw = _generate_with_deadline(prompt, schema)
        # Validate against the lenient base schema; invented paths are filtered below
        # instead of failing the whole summary.
        result = AISummary.model_validate_json(raw)
    except Exception as e:  # noqa: BLE001 - any AI failure must fall back, never 500
        log.warning("Gemini summary failed after %.1fs (%s); using placeholder.", time.monotonic() - started, _describe(e))
        return fallback, "ai_failed"

    log.info("Gemini summary ok in %.1fs.", time.monotonic() - started)
    link_sources = [note, terminal_text, transcript, git.diff, *links]
    return _to_summary(result, allowed, links, link_sources, fallback), "ready"


# ---------- Gemini call ----------

def _response_model(paths: list[str]) -> type[AISummary]:
    """AISummary with files[].path restricted to an enum of allowed paths."""
    if not paths:
        return AISummary
    file_model = create_model(
        "AIFile",
        __base__=AIFile,
        path=(Literal[tuple(paths)], Field(description=AIFile.model_fields["path"].description)),
    )
    return create_model(
        "AISummary",
        __base__=AISummary,
        files=(list[file_model], Field(description=AISummary.model_fields["files"].description)),
    )


def _generate_with_deadline(prompt: str, schema: type[AISummary]) -> str:
    """Primary model once; fallback model at most once, only for 429/5xx; hard total deadline."""
    deadline = time.monotonic() + AI_DEADLINE_SECONDS
    models = [config.GEMINI_MODEL]
    if config.GEMINI_FALLBACK_MODEL and config.GEMINI_FALLBACK_MODEL != config.GEMINI_MODEL:
        models.append(config.GEMINI_FALLBACK_MODEL)

    for i, model in enumerate(models):
        future = _executor.submit(_call_gemini, prompt, schema, model)
        try:
            text = future.result(timeout=max(deadline - time.monotonic(), 0.1))
            log.info("Gemini %s responded.", model)
            return text
        except FutureTimeout:
            raise TimeoutError(f"{model}: no response within the {AI_DEADLINE_SECONDS:.0f}s budget")
        except Exception as e:
            remaining = deadline - time.monotonic()
            is_last = i == len(models) - 1
            if is_last or not _is_retriable(e) or remaining < FALLBACK_MIN_REMAINING_SECONDS:
                if not is_last:
                    log.info("Gemini %s failed (%s); no fallback attempted.", model, _describe(e))
                raise
            log.info("Gemini %s failed (%s); trying fallback %s with %.1fs left.", model, _describe(e), models[i + 1], remaining)
    raise RuntimeError("unreachable")


def _call_gemini(prompt: str, schema: type[AISummary], model: str) -> str:
    # Low thinking for both models, optimized for latency. If a model rejects this
    # setting it returns 400, which is non-retriable: we go straight to the placeholder.
    response = _get_client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=prompts.SYSTEM_INSTRUCTION,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        ),
    )
    if not response.text:
        raise EmptyResponseError("empty or blocked response")
    return response.text


def _get_client() -> genai.Client:
    global _client, _client_key
    if _client is None or _client_key != config.GEMINI_API_KEY:
        _client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=int(AI_DEADLINE_SECONDS * 1000),  # backstop; the deadline above is authoritative
                retry_options=types.HttpRetryOptions(attempts=1),  # no SDK retries; fallback is handled above
            ),
        )
        _client_key = config.GEMINI_API_KEY
    return _client


def _is_retriable(e: Exception) -> bool:
    if isinstance(e, errors.APIError):
        return e.code == 429 or e.code >= 500
    return isinstance(e, httpx.TransportError) and not isinstance(e, httpx.TimeoutException)


def _describe(e: Exception) -> str:
    if isinstance(e, errors.APIError):
        return f"{type(e).__name__} {e.code} {e.status or ''}".strip()
    return type(e).__name__


# ---------- Post-processing: the second layer of defense ----------

def _to_summary(
    result: AISummary,
    allowed: list[tuple[str, str]],
    user_links: list[str],
    link_sources: list[str],
    fallback: Summary,
) -> Summary:
    allowed_paths = {path for path, _ in allowed}
    files: list[FileRef] = []
    for f in result.files:
        path = _match_allowed_path(f.path, allowed_paths)
        if path and path not in {x.path for x in files}:
            files.append(FileRef(path=path, reason=_clean(f.reason, 200)))
        if len(files) >= MAX_FILES:
            break

    known_urls = {_normalize_url(u) for text in link_sources for u in _URL.findall(text)}
    links: list[Link] = []
    for link in result.links:
        url = link.url.strip()
        if _normalize_url(url) in known_urls and url not in {x.url for x in links}:
            links.append(Link(title=_clean(link.title, 80) or url, url=url))
    for url in user_links:  # never lose a link the developer explicitly saved
        if _normalize_url(url) not in {_normalize_url(x.url) for x in links}:
            links.append(Link(title=url, url=url))

    return Summary(
        title=_clean(result.title, 80) or fallback.title,
        doing=_clean(result.doing, 600) or fallback.doing,
        problem=_clean(result.problem, 600),
        tried=_clean_list(result.tried),
        errors=[e for e in _clean_list(result.errors) if "[REDACTED]" not in e][:4],
        files=files or fallback.files,
        next_step=_clean(result.next_step, 200) or fallback.next_step,
        next_step_detail=_clean(result.next_step_detail, 600),
        links=links,
    )


def _match_allowed_path(path: str, allowed_paths: set[str]) -> str | None:
    """Maps a model-returned path to an allowed path, or None.

    An exact match always wins, so a real repo path like "a/main.py" is kept as is.
    Diff-style "a/" / "b/" prefixes are stripped only if the result is itself allowed.
    """
    path = path.strip().replace("\\", "/")
    if path in allowed_paths:
        return path
    path = path.removeprefix("./").lstrip("/")  # git paths never start with ./ or /
    if path in allowed_paths:
        return path
    for prefix in ("a/", "b/"):
        if path.startswith(prefix) and path[len(prefix):] in allowed_paths:
            return path[len(prefix):]
    return None


def _normalize_url(url: str) -> str:
    return url.strip().rstrip(".,;:").rstrip("/")


def _clean(text: str, limit: int) -> str:
    text = sanitize(text.strip())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _clean_list(items: list[str]) -> list[str]:
    return [c for c in (_clean(i, 300) for i in items) if c][:MAX_LIST_ITEMS]


# ---------- Placeholder used when AI is unavailable ----------

def _fallback_summary(
    git: GitContext,
    note: str,
    terminal_text: str,
    transcript: str,
    links: list[str],
    allowed: list[tuple[str, str]],
) -> Summary:
    n = len(git.changed_files)
    first_line = note.splitlines()[0].strip() if note else ""
    return Summary(
        title=_clip(first_line, 60) if first_line else f"Work on {git.branch}",
        doing=note or (f"Uncommitted changes to {n} file(s) on {git.branch}." if n else f"No uncommitted changes on {git.branch}."),
        problem=transcript,
        tried=[],
        errors=[line.strip() for line in terminal_text.splitlines() if line.strip()][-3:],
        files=[FileRef(path=path, reason=prompts.STATUS_LABELS.get(status, "changed").capitalize())
               for path, status in allowed[:MAX_FILES]],
        next_step=_last_sentence(note) or "Review your uncommitted changes.",
        next_step_detail="",
        links=[Link(title=url, url=url) for url in links],
    )


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _last_sentence(text: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    return sentences[-1] if sentences else ""
