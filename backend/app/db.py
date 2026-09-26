"""SQLite persistence: one table, JSON columns for nested data."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Optional

from . import config
from .schemas import Checkpoint, CheckpointListItem, GitContext, Summary

SCHEMA = """
CREATE TABLE IF NOT EXISTS checkpoints (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    repo_path     TEXT NOT NULL,
    repo_name     TEXT NOT NULL,
    branch        TEXT NOT NULL,
    status        TEXT NOT NULL,
    note          TEXT NOT NULL DEFAULT '',
    terminal_text TEXT NOT NULL DEFAULT '',
    transcript    TEXT NOT NULL DEFAULT '',
    git_json      TEXT NOT NULL,
    summary_json  TEXT
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at ON checkpoints (created_at);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect()) as conn:
        conn.executescript(SCHEMA)


def insert(
    *,
    repo_path: str,
    status: str,
    note: str,
    terminal_text: str,
    transcript: str,
    git: GitContext,
    summary: Optional[Summary],
) -> int:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            """INSERT INTO checkpoints
               (created_at, repo_path, repo_name, branch, status, note, terminal_text, transcript, git_json, summary_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                created_at, repo_path, git.repo_name, git.branch, status, note, terminal_text, transcript,
                git.model_dump_json(), summary.model_dump_json() if summary else None,
            ),
        )
        return cur.lastrowid


def list_all(repo_path: Optional[str] = None, limit: int = 100) -> list[CheckpointListItem]:
    query = """SELECT id, created_at, repo_path, repo_name, branch, status,
                      json_extract(summary_json, '$.title') AS title,
                      json_extract(summary_json, '$.next_step') AS next_step
               FROM checkpoints"""
    params: list = []
    if repo_path:
        query += " WHERE repo_path = ?"
        params.append(repo_path)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with closing(_connect()) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        CheckpointListItem(
            id=r["id"],
            created_at=r["created_at"],
            repo_path=r["repo_path"],
            repo_name=r["repo_name"],
            branch=r["branch"],
            status=r["status"],
            title=r["title"] or "Untitled checkpoint",
            next_step=r["next_step"] or "",
        )
        for r in rows
    ]


def get(checkpoint_id: int) -> Optional[Checkpoint]:
    with closing(_connect()) as conn:
        r = conn.execute("SELECT * FROM checkpoints WHERE id = ?", (checkpoint_id,)).fetchone()
    if r is None:
        return None
    return Checkpoint(
        id=r["id"],
        created_at=r["created_at"],
        repo_path=r["repo_path"],
        status=r["status"],
        note=r["note"],
        terminal_text=r["terminal_text"],
        transcript=r["transcript"],
        git=GitContext.model_validate_json(r["git_json"]),
        summary=Summary.model_validate_json(r["summary_json"]) if r["summary_json"] else None,
    )


def delete(checkpoint_id: int) -> bool:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM checkpoints WHERE id = ?", (checkpoint_id,))
        return cur.rowcount > 0
