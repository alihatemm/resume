import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, main

# Built by concatenation so no real-looking key literal lives in the repo.
FAKE_GOOGLE_KEY = "AIza" + "B" * 35


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com",
         "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
    )


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--no-verify", "-m", message)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A small git repo with one commit and a clean tree."""
    r = tmp_path / "demo-api"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "main.py").write_text("def get_user(headers):\n    return headers.get('Authorization')\n")
    (r / "README.md").write_text("# demo\n")
    commit_all(r, "initial commit")
    return r


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    with TestClient(main.app) as c:
        yield c
