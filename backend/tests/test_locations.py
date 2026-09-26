import json
import subprocess

import pytest

from app import ai, config
from app.git_context import allowed_files, capture
from app.locations import add_file_locations
from app.schemas import FileRef

from .conftest import commit_all, git

TEN_LINES = "".join(f"line_{i} = {i}\n" for i in range(1, 11))


def locate(repo, paths, terminal="", allowed=None):
    """Runs add_file_locations for the given paths; allowlist defaults to the real one."""
    ctx = capture(repo)
    if allowed is None:
        allowed = allowed_files(repo, ctx, [terminal])
    refs = [FileRef(path=p, reason="r") for p in paths]
    return {f.path: f for f in add_file_locations(repo, ctx, refs, allowed, terminal)}


@pytest.fixture
def lines_repo(repo):
    (repo / "lines.py").write_text(TEN_LINES)
    commit_all(repo, "add lines.py")
    return repo


def edit_lines(path, changes: dict[int, str | None]):
    """1-based line edits; None deletes the line."""
    lines = path.read_text().splitlines(keepends=True)
    for n in sorted(changes, reverse=True):
        if changes[n] is None:
            del lines[n - 1]
        else:
            lines[n - 1] = changes[n] + "\n"
    path.write_text("".join(lines))


# ---------- diff-derived lines ----------

def test_modified_file_uses_first_changed_line(lines_repo):
    edit_lines(lines_repo / "lines.py", {5: "line_5 = 'changed'"})
    f = locate(lines_repo, ["lines.py"])["lines.py"]
    assert f.line == 5
    assert f.abs_path == str((lines_repo / "lines.py").resolve())


def test_first_of_multiple_hunks_wins(lines_repo):
    edit_lines(lines_repo / "lines.py", {3: "a = 1", 8: "b = 2"})
    assert locate(lines_repo, ["lines.py"])["lines.py"].line == 3


def test_deletion_only_hunk_points_near_removed_code(lines_repo):
    edit_lines(lines_repo / "lines.py", {6: None})
    assert locate(lines_repo, ["lines.py"])["lines.py"].line == 5


def test_staged_and_unstaged_changes_both_count(lines_repo):
    edit_lines(lines_repo / "lines.py", {7: "staged = 1"})
    git(lines_repo, "add", "lines.py")
    edit_lines(lines_repo / "lines.py", {9: "unstaged = 1"})
    assert locate(lines_repo, ["lines.py"])["lines.py"].line == 7


# ---------- file states ----------

def test_untracked_file_has_path_but_no_line(repo):
    (repo / "new_mod.py").write_text("x = 1\n")
    f = locate(repo, ["new_mod.py"])["new_mod.py"]
    assert f.abs_path == str((repo / "new_mod.py").resolve())
    assert f.line is None


def test_staged_new_file_has_no_line(repo):
    (repo / "added.py").write_text("x = 1\ny = 2\n")
    git(repo, "add", "added.py")
    f = locate(repo, ["added.py"])["added.py"]
    assert f.abs_path is not None and f.line is None


def test_renamed_file_uses_new_path(lines_repo):
    git(lines_repo, "mv", "lines.py", "renamed.py")
    f = locate(lines_repo, ["renamed.py"])["renamed.py"]
    assert f.abs_path == str((lines_repo / "renamed.py").resolve())
    assert f.line is None  # appears as a whole new file to a path-limited diff


def test_deleted_file_is_kept_without_location(lines_repo):
    (lines_repo / "lines.py").unlink()
    f = locate(lines_repo, ["lines.py"])["lines.py"]
    assert (f.path, f.reason, f.abs_path, f.line) == ("lines.py", "r", None, None)


# ---------- terminal-derived lines ----------

def test_unchanged_mentioned_file_uses_python_traceback_line(repo):
    terminal = f'Traceback (most recent call last):\n  File "{repo}/main.py", line 2, in get_user\nKeyError: \'authorization\''
    f = locate(repo, ["main.py"], terminal)["main.py"]
    assert f.line == 2
    assert f.abs_path == str((repo / "main.py").resolve())


def test_path_line_col_style(repo):
    assert locate(repo, ["main.py"], "main.py:2:5: E501 line too long")["main.py"].line == 2


def test_tsc_style(repo):
    (repo / "app.ts").write_text("let a = 1\nlet b: string = 2\n")
    commit_all(repo, "add ts")
    assert locate(repo, ["app.ts"], "app.ts(2,5): error TS2322")["app.ts"].line == 2


def test_terminal_line_beats_diff_line(lines_repo):
    edit_lines(lines_repo / "lines.py", {5: "changed = 1"})
    assert locate(lines_repo, ["lines.py"], "lines.py:9: AssertionError")["lines.py"].line == 9


def test_last_valid_terminal_reference_wins(lines_repo):
    terminal = 'File "lines.py", line 3\nFile "lines.py", line 7\nFile "lines.py", line 99'
    assert locate(lines_repo, ["lines.py"], terminal)["lines.py"].line == 7


def test_out_of_range_terminal_line_falls_back_to_diff(lines_repo):
    edit_lines(lines_repo / "lines.py", {5: "changed = 1"})
    assert locate(lines_repo, ["lines.py"], "lines.py:99")["lines.py"].line == 5


def test_out_of_range_terminal_line_on_unchanged_file_is_null(repo):
    assert locate(repo, ["main.py"], "main.py:99")["main.py"].line is None


def test_absolute_path_from_another_repo_does_not_match(repo, tmp_path):
    terminal = f'File "{tmp_path}/other-repo/main.py", line 2'
    f = locate(repo, ["main.py"], terminal, allowed=[("main.py", "mentioned")])["main.py"]
    assert f.line is None


def test_relative_path_from_subdirectory_matches(repo):
    (repo / "backend" / "tests").mkdir(parents=True)
    (repo / "backend" / "tests" / "test_x.py").write_text("a\nb\nc\n")
    commit_all(repo, "add test")
    allowed = [("backend/tests/test_x.py", "mentioned")]
    f = locate(repo, ["backend/tests/test_x.py"], "tests/test_x.py:3: AssertionError", allowed=allowed)
    assert f["backend/tests/test_x.py"].line == 3


def test_bare_name_does_not_match_nested_file(repo):
    (repo / "pkg").mkdir()
    (repo / "pkg" / "util.py").write_text("a\nb\n")
    commit_all(repo, "add util")
    f = locate(repo, ["pkg/util.py"], "util.py:2", allowed=[("pkg/util.py", "mentioned")])["pkg/util.py"]
    assert f.abs_path is not None and f.line is None


# ---------- path safety ----------

@pytest.mark.parametrize("bad", ["../outside.py", "/etc/passwd", "~/x.py", "pkg/../../outside.py", "a\\b.py"])
def test_unsafe_paths_get_no_location_even_if_allowlisted(repo, tmp_path, bad):
    (tmp_path / "outside.py").write_text("secret = 1\n")
    f = locate(repo, [bad], allowed=[(bad, "M")])[bad]
    assert f.abs_path is None and f.line is None


def test_path_not_in_allowlist_gets_no_location(repo):
    f = locate(repo, ["main.py"], allowed=[])["main.py"]
    assert f.abs_path is None and f.line is None


def test_symlink_escaping_repo_is_rejected(repo, tmp_path):
    outside = tmp_path / "outside_secret.py"
    outside.write_text("secret = 1\n")
    (repo / "link.py").symlink_to(outside)
    f = locate(repo, ["link.py"], "link.py:1", allowed=[("link.py", "??")])["link.py"]
    assert f.abs_path is None and f.line is None


def test_excluded_file_is_rejected_even_if_allowlisted(repo):
    (repo / ".env").write_text("A=1\n")
    f = locate(repo, [".env"], allowed=[(".env", "??")])[".env"]
    assert f.abs_path is None


def test_real_directory_named_a_is_fine(repo):
    (repo / "a").mkdir()
    (repo / "a" / "main.py").write_text("x = 1\n")
    f = locate(repo, ["a/main.py"])["a/main.py"]
    assert f.abs_path == str((repo / "a" / "main.py").resolve())


def test_incoming_line_and_abs_path_are_ignored(repo):
    ctx = capture(repo)
    refs = [FileRef(path="main.py", reason="r", line=999, abs_path="/evil/path.py")]
    [f] = add_file_locations(repo, ctx, refs, [("main.py", "mentioned")], "")
    assert f.abs_path == str((repo / "main.py").resolve())
    assert f.line is None


# ---------- through the API ----------

def test_locations_are_stored_and_get_needs_no_gemini_or_git(client, repo, monkeypatch):
    (repo / "middleware.py").write_text("def strip(scope):\n    return scope\n")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    gemini_calls = []

    def fake_gemini(prompt, schema, model):
        gemini_calls.append(model)
        return json.dumps({
            "title": "t", "doing": "d", "problem": "p", "tried": [], "errors": [],
            "files": [{"path": "middleware.py", "reason": "changed"}, {"path": "main.py", "reason": "crash site"}],
            "next_step": "n", "next_step_detail": "", "links": [],
        })

    monkeypatch.setattr(ai, "_call_gemini", fake_gemini)
    res = client.post("/api/checkpoints", json={
        "repo_path": str(repo),
        "terminal_text": f'  File "{repo}/main.py", line 2, in get_user\nKeyError: \'authorization\'',
    })
    cp = res.json()
    assert cp["status"] == "ready"
    files = {f["path"]: f for f in cp["summary"]["files"]}
    assert files["main.py"]["line"] == 2
    assert files["main.py"]["abs_path"] == str((repo / "main.py").resolve())
    assert files["middleware.py"]["line"] is None  # untracked
    assert len(gemini_calls) == 1

    # Restore path: any Gemini call or subprocess (git) call would blow up.
    def boom(*args, **kwargs):
        raise AssertionError("restore must not call Gemini or git")

    monkeypatch.setattr(ai, "_call_gemini", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    got = client.get(f"/api/checkpoints/{cp['id']}")
    assert got.status_code == 200
    assert got.json() == cp
    assert client.get("/api/checkpoints").status_code == 200


# ---------- suffix ambiguity ----------

@pytest.fixture
def two_test_dirs(repo):
    for top in ("backend", "frontend"):
        (repo / top / "tests").mkdir(parents=True)
        (repo / top / "tests" / "test_api.py").write_text(TEN_LINES)
    commit_all(repo, "add two test_api.py files")
    return repo


def test_unique_suffix_reference_resolves(two_test_dirs):
    allowed = [("backend/tests/test_api.py", "mentioned")]  # only one allowed file ends with tests/test_api.py
    f = locate(two_test_dirs, ["backend/tests/test_api.py"], "tests/test_api.py:4: AssertionError", allowed=allowed)
    assert f["backend/tests/test_api.py"].line == 4


def test_ambiguous_suffix_reference_matches_neither_file(two_test_dirs):
    edit_lines(two_test_dirs / "backend" / "tests" / "test_api.py", {6: "changed = 1"})
    allowed = [("backend/tests/test_api.py", "M"), ("frontend/tests/test_api.py", "mentioned")]
    paths = ["backend/tests/test_api.py", "frontend/tests/test_api.py"]
    f = locate(two_test_dirs, paths, "tests/test_api.py:4: AssertionError", allowed=allowed)
    assert f["backend/tests/test_api.py"].line == 6      # falls back to the diff line
    assert f["frontend/tests/test_api.py"].line is None  # unchanged: falls back to null
    assert all(x.abs_path for x in f.values())


def test_exact_relative_path_wins_over_same_suffix_or_name(two_test_dirs):
    repo = two_test_dirs
    (repo / "tests").mkdir()
    (repo / "tests" / "test_api.py").write_text(TEN_LINES)
    (repo / "pkg").mkdir()
    (repo / "pkg" / "main.py").write_text(TEN_LINES)
    commit_all(repo, "add root tests/test_api.py and pkg/main.py")
    paths = ["tests/test_api.py", "backend/tests/test_api.py", "main.py", "pkg/main.py"]
    allowed = [(p, "mentioned") for p in paths]
    f = locate(repo, paths, "tests/test_api.py:5\nmain.py:2", allowed=allowed)
    assert f["tests/test_api.py"].line == 5              # exact repo-relative match
    assert f["backend/tests/test_api.py"].line is None   # token names another allowed file exactly
    assert f["main.py"].line == 2                        # exact match on a bare root file name
    assert f["pkg/main.py"].line is None
