import shutil
import sqlite3

import pytest

from app import config, since
from app.git_context import GitError

from .conftest import FAKE_GOOGLE_KEY, commit_all, git


def checkpoint(client, repo):
    res = client.post("/api/checkpoints", json={"repo_path": str(repo), "note": "wip"})
    assert res.status_code == 201, res.text
    return res.json()


def since_for(client, cp):
    res = client.get(f"/api/checkpoints/{cp['id']}/since")
    assert res.status_code == 200, res.text
    return res.json()


def add_commit(repo, name, content="x = 1\n", message=None):
    (repo / name).write_text(content)
    commit_all(repo, message or f"Add {name}")


# ---------- normal path ----------

def test_unchanged(client, repo):
    cp = checkpoint(client, repo)
    s = since_for(client, cp)
    assert s["status"] == "unchanged"
    assert s["message"] == "Nothing has been committed since this checkpoint."
    assert s["current_head"] == cp["git"]["head_sha"]
    assert (s["commits_ahead"], s["commits_behind"], s["files_changed"]) == (0, 0, 0)
    assert s["uncommitted_files"] == 0


def test_unchanged_reports_uncommitted_files(client, repo):
    cp = checkpoint(client, repo)
    (repo / "main.py").write_text("changed = True\n")
    s = since_for(client, cp)
    assert s["status"] == "unchanged"
    assert s["uncommitted_files"] == 1
    assert s["uncommitted_paths"] == ["main.py"]


def test_new_commits_and_files(client, repo):
    cp = checkpoint(client, repo)
    add_commit(repo, "auth.py", message="Add auth helpers")
    (repo / "main.py").write_text("print('v2')\n")
    commit_all(repo, "Update main")
    (repo / "README.md").unlink()
    commit_all(repo, "Remove README")

    s = since_for(client, cp)
    assert s["status"] == "changed"
    assert s["history"] == "linear"
    assert (s["commits_ahead"], s["commits_behind"]) == (3, 0)
    assert [c["subject"] for c in s["commits"]] == ["Remove README", "Update main", "Add auth helpers"]
    assert all(c["author"] == "Test" and c["date"] and len(c["sha"]) >= 7 for c in s["commits"])
    assert {f["path"]: f["status"] for f in s["files"]} == {"auth.py": "A", "main.py": "M", "README.md": "D"}
    assert s["files_changed"] == 3
    assert s["message"] == "3 commits and 3 files changed since you saved this checkpoint."
    assert s["current_head"] != s["saved_head"]
    assert s["current_branch"] == s["saved_branch"] == "main"


def test_commit_without_file_changes(client, repo):
    cp = checkpoint(client, repo)
    git(repo, "commit", "-q", "--allow-empty", "-m", "Empty commit")
    s = since_for(client, cp)
    assert s["message"] == "1 commit since you saved this checkpoint, with no file changes."


# ---------- bounds ----------

def test_output_is_bounded(client, repo):
    cp = checkpoint(client, repo)
    for i in range(30):
        (repo / f"mod{i}.py").write_text(f"v = {i}\n")
    commit_all(repo, "Add 30 modules")
    for i in range(14):
        (repo / "main.py").write_text(f"version = {i}\n")
        commit_all(repo, f"Bump {i}")

    res = client.get(f"/api/checkpoints/{cp['id']}/since")
    s = res.json()
    assert s["commits_ahead"] == 15
    assert len(s["commits"]) == 10 and s["commits_truncated"]
    assert s["files_changed"] == 31
    assert len(s["files"]) == 20 and s["files_truncated"]
    assert "diff" not in s
    assert len(res.content) < 6_000


def test_subject_is_capped_and_sanitized(client, repo):
    cp = checkpoint(client, repo)
    add_commit(repo, "a.py", message=f"Rotate key {FAKE_GOOGLE_KEY} " + "x" * 200)
    s = since_for(client, cp)
    subject = s["commits"][0]["subject"]
    assert FAKE_GOOGLE_KEY not in subject and "[REDACTED]" in subject
    assert len(subject) <= since.MAX_SUBJECT_CHARS


# ---------- history changes ----------

def test_head_moved_backward(client, repo):
    add_commit(repo, "a.py")
    add_commit(repo, "b.py")
    cp = checkpoint(client, repo)
    git(repo, "reset", "-q", "--hard", "HEAD~2")

    s = since_for(client, cp)
    assert s["status"] == "changed"
    assert s["history"] == "behind"
    assert (s["commits_ahead"], s["commits_behind"]) == (0, 2)
    assert s["commits"] == []
    assert s["message"] == "Current HEAD is 2 commits behind the saved checkpoint."


def test_history_diverged_and_branch_switch(client, repo):
    add_commit(repo, "a.py")
    cp = checkpoint(client, repo)
    git(repo, "checkout", "-q", "-b", "feature", "HEAD~1")
    add_commit(repo, "b.py", message="Feature work")

    s = since_for(client, cp)
    assert s["history"] == "diverged"
    assert (s["commits_ahead"], s["commits_behind"]) == (1, 1)
    assert s["current_branch"] == "feature"
    assert s["message"] == (
        "Repository history has diverged from this checkpoint: current HEAD is 1 commit ahead and "
        "1 commit behind the saved checkpoint. You're on feature now (checkpoint was on main)."
    )


def test_detached_head(client, repo):
    cp = checkpoint(client, repo)
    add_commit(repo, "a.py")
    git(repo, "checkout", "-q", "--detach")
    s = since_for(client, cp)
    assert s["current_branch"] == "HEAD (detached)"
    assert s["commits_ahead"] == 1 and s["history"] == "linear"


def test_repo_had_no_commits_at_checkpoint(client, tmp_path):
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    git(fresh, "init", "-q", "-b", "main")
    (fresh / "app.py").write_text("print('hi')\n")
    cp = checkpoint(client, fresh)
    assert cp["git"]["head_sha"] == ""

    assert since_for(client, cp)["status"] == "unchanged"

    commit_all(fresh, "First commit")
    add_commit(fresh, "b.py")
    s = since_for(client, cp)
    assert s["status"] == "changed"
    assert s["commits_ahead"] == 2
    assert {f["path"] for f in s["files"]} == {"app.py", "b.py"}


# ---------- unavailable (never a 500) ----------

def test_repo_missing(client, repo):
    cp = checkpoint(client, repo)
    repo.rename(repo.with_name("moved-away"))
    s = since_for(client, cp)
    assert (s["status"], s["reason"]) == ("unavailable", "repo_missing")
    assert s["saved_head"] == cp["git"]["head_sha"]


def test_not_a_repo_anymore(client, repo):
    cp = checkpoint(client, repo)
    shutil.rmtree(repo / ".git")
    s = since_for(client, cp)
    assert (s["status"], s["reason"]) == ("unavailable", "not_a_repo")


def test_saved_commit_no_longer_exists(client, repo):
    add_commit(repo, "a.py")
    cp = checkpoint(client, repo)
    git(repo, "commit", "-q", "--amend", "-m", "Rewritten")
    git(repo, "reflog", "expire", "--expire=now", "--all")
    git(repo, "gc", "-q", "--prune=now")
    s = since_for(client, cp)
    assert (s["status"], s["reason"]) == ("unavailable", "commit_missing")
    assert cp["git"]["head_sha"] in s["message"]


@pytest.mark.parametrize("error", [GitError("git log timed out after 10s."), RuntimeError("boom")])
def test_git_failure_is_unavailable_not_500(client, repo, monkeypatch, error):
    cp = checkpoint(client, repo)

    def failing_git(*args, **kwargs):
        raise error

    monkeypatch.setattr(since, "_git", failing_git)
    s = since_for(client, cp)
    assert (s["status"], s["reason"]) == ("unavailable", "git_error")
    assert "boom" not in s["message"] and "timed out" not in s["message"]  # details stay in server logs


# ---------- API contract ----------

def test_unknown_checkpoint_is_404(client):
    res = client.get("/api/checkpoints/999/since")
    assert res.status_code == 404
    assert res.json()["detail"] == "Checkpoint 999 not found."


def test_endpoint_does_not_modify_the_checkpoint(client, repo):
    cp = checkpoint(client, repo)
    add_commit(repo, "a.py")
    with sqlite3.connect(config.DB_PATH) as conn:
        before = conn.execute("SELECT * FROM checkpoints").fetchall()
    since_for(client, cp)
    since_for(client, cp)
    with sqlite3.connect(config.DB_PATH) as conn:
        assert conn.execute("SELECT * FROM checkpoints").fetchall() == before
    assert client.get(f"/api/checkpoints/{cp['id']}").json() == cp
