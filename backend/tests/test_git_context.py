import pytest

from app import git_context
from app.git_context import GitError, allowed_files, capture, resolve_repo, sanitize

from .conftest import FAKE_GOOGLE_KEY, commit_all, git


def test_captures_branch_head_changes_and_untracked(repo):
    (repo / "main.py").write_text("def get_user(headers):\n    return headers.get('authorization')\n")
    (repo / "middleware.py").write_text("def strip_headers(req):\n    return req\n")

    ctx = capture(resolve_repo(str(repo)))

    assert ctx.repo_name == "demo-api"
    assert ctx.branch == "main"
    assert ctx.head_sha
    assert ctx.recent_commits[0].endswith("initial commit")
    statuses = {f.path: f.status for f in ctx.changed_files}
    assert statuses == {"main.py": "M", "middleware.py": "??"}
    assert "headers.get('authorization')" in ctx.diff
    assert "def strip_headers" in ctx.diff  # untracked file content included
    assert not ctx.diff_truncated


def test_resolve_repo_returns_root_from_subdirectory(repo):
    (repo / "pkg").mkdir()
    assert resolve_repo(str(repo / "pkg")) == repo.resolve()


@pytest.mark.parametrize("bad", ["", "relative/path", "/definitely/not/here"])
def test_invalid_paths_raise(bad):
    with pytest.raises(GitError):
        resolve_repo(bad)


def test_non_repo_directory_raises(tmp_path):
    with pytest.raises(GitError, match="Not a git repository"):
        resolve_repo(str(tmp_path))


def test_env_file_listed_but_never_read(repo):
    (repo / ".env").write_text(f"GEMINI_API_KEY={FAKE_GOOGLE_KEY}\n")

    ctx = capture(repo)

    assert ".env" in [f.path for f in ctx.changed_files]
    assert FAKE_GOOGLE_KEY not in ctx.diff
    assert ".env (excluded)" in ctx.diff


def test_secrets_in_tracked_diff_are_redacted(repo):
    (repo / "settings.py").write_text(f'API_KEY = "{FAKE_GOOGLE_KEY}"\n')

    ctx = capture(repo)

    assert FAKE_GOOGLE_KEY not in ctx.diff
    assert "[REDACTED]" in ctx.diff


@pytest.mark.parametrize(
    "secret",
    [
        FAKE_GOOGLE_KEY,
        "sk-" + "a1" * 15,
        "ghp_" + "Z" * 36,
        "AKIA" + "ABCDEFGHIJKLMNOP",
        "-----BEGIN RSA PRIVATE KEY-----\nabc\ndef\n-----END RSA PRIVATE KEY-----",
    ],
)
def test_sanitize_known_formats(secret):
    out = sanitize(f"before {secret} after")
    assert secret not in out
    assert "[REDACTED]" in out
    assert out.startswith("before") and out.endswith("after")


def test_sanitize_keeps_names_and_normal_code():
    assert sanitize("DB_PASSWORD=hunter2hunter2") == "DB_PASSWORD=[REDACTED]"
    assert sanitize("Authorization: Bearer " + "t" * 30) == "Authorization: Bearer [REDACTED]"
    code = "token = request.headers.get('Authorization')"
    assert sanitize(code) == code


def test_lockfile_and_binary_contents_excluded(repo):
    (repo / "package-lock.json").write_text('{"lockfileVersion": 3}\n')
    (repo / "logo.bin").write_bytes(b"\x00\x01\x02binarydata")
    commit_all(repo, "add lock + binary")
    (repo / "package-lock.json").write_text('{"lockfileVersion": 3, "changed": "LOCKMARKER"}\n')
    (repo / "logo.bin").write_bytes(b"\x00\x01\x02BINARYMARKER")

    ctx = capture(repo)

    assert "LOCKMARKER" not in ctx.diff
    assert "BINARYMARKER" not in ctx.diff
    assert "package-lock.json (excluded)" in ctx.diff
    assert "logo.bin (binary)" in ctx.diff


def test_large_file_diff_is_omitted(repo):
    (repo / "big.py").write_text("")
    commit_all(repo, "add big.py")
    (repo / "big.py").write_text("".join(f"x_{i} = {i}\n" for i in range(600)))
    (repo / "big_new.py").write_text("".join(f"n_{i} = {i}\n" for i in range(600)))

    ctx = capture(repo)

    assert "x_599" not in ctx.diff and "n_599" not in ctx.diff
    assert "big.py (600 lines changed)" in ctx.diff
    assert "big_new.py (untracked, over 400 lines)" in ctx.diff


def test_total_diff_is_capped(repo, monkeypatch):
    monkeypatch.setattr(git_context, "MAX_DIFF_CHARS", 2_000)
    for n in range(10):
        (repo / f"mod{n}.py").write_text("")
    commit_all(repo, "empty modules")
    for n in range(10):
        (repo / f"mod{n}.py").write_text("".join(f"value_{n}_{i} = '{'y' * 40}'\n" for i in range(20)))

    ctx = capture(repo)

    assert ctx.diff_truncated
    assert "[diff truncated: size limit reached]" in ctx.diff
    body = ctx.diff.split("\n[diff truncated")[0]
    assert len(body) <= 2_000


def test_excluded_dirs_are_not_listed(repo):
    (repo / "node_modules" / "pkg").mkdir(parents=True)
    (repo / "node_modules" / "pkg" / "index.js").write_text("module.exports = 1\n")

    ctx = capture(repo)

    assert ctx.changed_files == []


# --- Unusual cases (cheap, so included) ---

def test_repo_with_no_commits(tmp_path):
    r = tmp_path / "fresh"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    (r / "app.py").write_text("print('hi')\n")

    ctx = capture(resolve_repo(str(r)))

    assert ctx.head_sha == ""
    assert ctx.branch == "main"
    assert ctx.recent_commits == []
    assert "print('hi')" in ctx.diff


def test_detached_head(repo):
    git(repo, "checkout", "-q", "--detach")
    assert capture(repo).branch == "HEAD (detached)"


def test_allowed_files_only_verified_tracked_mentions(repo):
    (repo / "src").mkdir()
    (repo / "src" / "helpers.py").write_text("x = 1\n")
    (repo / "lib").mkdir()
    (repo / "lib" / "helpers.py").write_text("x = 2\n")  # bare "helpers.py" is now ambiguous
    (repo / "src" / "routes.py").write_text("y = 1\n")
    (repo / ".env").write_text("A=1\n")
    commit_all(repo, "add src")
    (repo / "scratch.py").write_text("z = 1\n")  # untracked, so it's a changed file

    text = (
        'File "/Users/me/demo-api/src/routes.py", line 3\n'  # absolute path -> src/routes.py
        "see main.py, helpers.py, domain.py, ghost.py and .env\n"  # exact / ambiguous / no / missing / excluded
    )
    allowed = dict(allowed_files(repo, capture(repo), [text]))

    assert allowed == {"scratch.py": "??", "main.py": "mentioned", "src/routes.py": "mentioned"}
