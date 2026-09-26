"""The shared contract between backend and frontend.

frontend/src/types.ts mirrors these models. If you change one, change the other.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- What Gemini returns (structured output schema) ----------

class AIFile(BaseModel):
    path: str = Field(description="Repo-relative path. MUST be one of the changed files provided.")
    reason: str = Field(description="One short sentence: why this file matters right now.")


class AILink(BaseModel):
    title: str
    url: str


class AISummary(BaseModel):
    title: str = Field(description="3-8 word title for this work session.")
    doing: str = Field(description="What the developer was working on, 1-2 sentences.")
    problem: str = Field(description="The current blocker or open question, 1-2 sentences.")
    tried: list[str] = Field(description="Things already attempted, one per item.")
    errors: list[str] = Field(description="Key error messages or observations, verbatim where possible.")
    files: list[AIFile] = Field(description="Most important files, most important first. Max 4.")
    next_step: str = Field(description="The single concrete next action, one imperative sentence.")
    next_step_detail: str = Field(description="1-3 sentences on how to do the next step.")
    links: list[AILink] = Field(description="Only URLs present in the provided context. Empty if none.")


# ---------- Git context captured by the backend ----------

class ChangedFile(BaseModel):
    path: str
    status: str  # e.g. "M", "A", "D", "??"


class GitContext(BaseModel):
    repo_name: str
    branch: str
    head_sha: str
    changed_files: list[ChangedFile]
    recent_commits: list[str]
    diff: str
    diff_truncated: bool = False


# ---------- Stored / returned checkpoint ----------

class FileRef(BaseModel):
    path: str
    reason: str
    line: Optional[int] = None  # computed from the diff, never from the AI
    abs_path: Optional[str] = None  # used to build vscode://file/ links


class Link(BaseModel):
    title: str
    url: str


class Summary(BaseModel):
    title: str
    doing: str
    problem: str
    tried: list[str]
    errors: list[str]
    files: list[FileRef]
    next_step: str
    next_step_detail: str
    links: list[Link]


class CheckpointCreate(BaseModel):
    repo_path: str
    note: str = ""
    terminal_text: str = ""
    transcript: str = ""
    links: list[str] = []


class Checkpoint(BaseModel):
    id: int
    created_at: str  # ISO 8601 UTC
    repo_path: str
    status: Literal["ready", "ai_failed"]
    note: str
    terminal_text: str
    transcript: str
    git: GitContext
    summary: Optional[Summary] = None


class CheckpointListItem(BaseModel):
    id: int
    created_at: str
    repo_path: str
    repo_name: str
    branch: str
    status: Literal["ready", "ai_failed"]
    title: str
    next_step: str


# ---------- Since you left (computed on request, never stored) ----------

class SinceCommit(BaseModel):
    sha: str  # short
    subject: str
    author: str
    date: str  # ISO 8601 author date


class SinceYouLeft(BaseModel):
    status: Literal["changed", "unchanged", "unavailable"]
    reason: Optional[Literal["repo_missing", "not_a_repo", "commit_missing", "git_error"]] = None
    message: str  # human-readable summary, safe to show as-is
    history: Literal["linear", "behind", "diverged"] = "linear"
    saved_head: str
    current_head: Optional[str] = None
    saved_branch: str
    current_branch: Optional[str] = None
    commits_ahead: int = 0  # commits in current HEAD that were not in the saved commit
    commits_behind: int = 0  # commits in the saved commit that current HEAD no longer has
    commits: list[SinceCommit] = []  # newest first, bounded
    commits_truncated: bool = False
    files_changed: int = 0  # total files changed between saved commit and current HEAD
    files: list[ChangedFile] = []  # bounded
    files_truncated: bool = False
    uncommitted_files: int = 0
    uncommitted_paths: list[str] = []  # bounded
