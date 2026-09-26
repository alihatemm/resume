"""Turns captured context into a structured Summary.

M1: a deterministic placeholder built only from the user's own inputs and git
metadata — no AI call. M2 replaces the body of summarize() with Gemini; the
signature stays the same.
"""

import re

from .schemas import FileRef, GitContext, Link, Summary

MAX_FILES = 4
STATUS_LABELS = {
    "M": "Modified",
    "A": "Added",
    "D": "Deleted",
    "R": "Renamed",
    "C": "Copied",
    "U": "Merge conflict",
    "??": "New file (untracked)",
}


def summarize(git: GitContext, note: str, terminal_text: str, transcript: str, links: list[str]) -> Summary:
    n = len(git.changed_files)
    first_line = note.splitlines()[0].strip() if note else ""
    return Summary(
        title=_clip(first_line, 60) if first_line else f"Work on {git.branch}",
        doing=note or (f"Uncommitted changes to {n} file(s) on {git.branch}." if n else f"No uncommitted changes on {git.branch}."),
        problem=transcript,
        tried=[],
        errors=[line.strip() for line in terminal_text.splitlines() if line.strip()][-3:],
        files=[FileRef(path=f.path, reason=STATUS_LABELS.get(f.status, "Changed")) for f in git.changed_files[:MAX_FILES]],
        next_step=_last_sentence(note) or "Review your uncommitted changes.",
        next_step_detail="",
        links=[Link(title=url, url=url) for url in links],
    )


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _last_sentence(text: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    return sentences[-1] if sentences else ""
