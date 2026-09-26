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
