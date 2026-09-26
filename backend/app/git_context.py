"""Captures bounded, sanitized git context for a local repository.

Everything returned from here is safe to store and to send to an AI model:
secret-looking files are never read, the diff is size-capped, and
secret-looking strings are redacted.
"""

import os
import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from .schemas import ChangedFile, GitContext

MAX_CHANGED_FILES = 200
MAX_DIFF_CHARS = 30_000
MAX_FILE_LINES_CHANGED = 400
MAX_UNTRACKED_FILES = 5
MAX_UNTRACKED_BYTES = 8_000
MAX_OMITTED_NOTES = 20
GIT_TIMEOUT_SECONDS = 10

# Git's well-known empty tree: lets us diff a repo that has no commits yet.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# Files inside these directories are dropped entirely (not even listed).
EXCLUDED_DIRS = {"node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".git", ".next"}

# Files matching these names are listed as changed, but their contents are never read.
EXCLUDED_NAMES = [
    # secrets
    ".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "credentials*", "*.p12",
    # lockfiles / generated
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "cargo.lock",
    "*.min.js", "*.min.css", "*.map",
    # binary / data
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.ico", "*.pdf", "*.zip", "*.gz", "*.tar",
    "*.woff", "*.woff2", "*.ttf", "*.mp3", "*.mp4", "*.webm", "*.db", "*.sqlite", "*.sqlite3",
]

REDACTED = "[REDACTED]"
_SECRET_NAME = r"[A-Za-z0-9_]*(?:api[_-]?key|secret|token|passw(?:or)?d)[A-Za-z0-9_]*"
SECRET_PATTERNS = [
    # PEM private keys (terminated, or running to the end of a truncated text)
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:.*?-----END [A-Z ]*PRIVATE KEY-----|.*\Z)", re.S), REDACTED),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), REDACTED),                   # Google / Gemini
    (re.compile(r"sk-(?:proj-|ant-)?[A-Za-z0-9_\-]{20,}"), REDACTED),    # OpenAI / Anthropic style
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), REDACTED),              # GitHub tokens
    (re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), REDACTED),
    (re.compile(r"AKIA[0-9A-Z]{16}"), REDACTED),                        # AWS access key id
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), REDACTED),            # Slack
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{20,}"), r"\1" + REDACTED),
    # NAME = "literal"  (e.g. API_KEY = "abc123...")
    (re.compile(rf"(?i)\b({_SECRET_NAME}\s*[=:]\s*)([\"'])[^\"'\s]{{8,}}\2"), r"\1\2" + REDACTED + r"\2"),
    # NAME=value at the start of a line (.env style)
    (re.compile(rf"(?im)^([+\- ]?\s*(?:export\s+)?{_SECRET_NAME}=)\S{{8,}}$"), r"\1" + REDACTED),
]


class GitError(Exception):
    """A user-facing problem with the repository path or git itself."""


def sanitize(text: str) -> str:
    """Replaces secret-looking substrings with [REDACTED]."""
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def is_excluded(path: str) -> bool:
    return _in_excluded_dir(path) or any(fnmatch(PurePosixPath(path).name.lower(), p) for p in EXCLUDED_NAMES)


def _in_excluded_dir(path: str) -> bool:
    return any(part in EXCLUDED_DIRS for part in PurePosixPath(path).parts[:-1])


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "GIT_OPTIONAL_LOCKS": "0",  # never write index.lock into the user's repo
        "GIT_LITERAL_PATHSPECS": "1",
        "GIT_PAGER": "cat",
        "LC_ALL": "C",
    }
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "-c", "core.quotepath=false", *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
            env=env,
        )
    except FileNotFoundError:
        raise GitError("git is not installed or not on PATH.")
    except subprocess.TimeoutExpired:
        raise GitError(f"git {args[0]} timed out after {GIT_TIMEOUT_SECONDS}s.")
    if check and result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {args[0]} failed.")
    return result


def resolve_repo(path: str) -> Path:
    """Validates a user-supplied path and returns the repository root."""
    if not path or not path.strip():
        raise GitError("Repository path is required.")
    p = Path(path.strip()).expanduser()
    if not p.is_absolute():
        raise GitError(f"Repository path must be absolute: {path}")
    if not p.exists():
        raise GitError(f"Path does not exist: {p}")
    if not p.is_dir():
        raise GitError(f"Path is not a directory: {p}")
    result = _git(p, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise GitError(f"Not a git repository: {p}")
    return Path(result.stdout.strip()).resolve()


def capture(root: Path) -> GitContext:
    """Captures branch, HEAD, changed files, recent commits and a bounded diff."""
    branch_result = _git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False)
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "HEAD (detached)"

    head_result = _git(root, "rev-parse", "--short", "--verify", "-q", "HEAD", check=False)
    head_sha = head_result.stdout.strip() if head_result.returncode == 0 else ""

    recent_commits = []
    if head_sha:
        log = _git(root, "log", "-5", "--oneline", "--no-decorate").stdout
        recent_commits = [sanitize(line) for line in log.splitlines() if line.strip()]

    changed_files = _changed_files(root)
    diff, truncated = _bounded_diff(root, head_sha or EMPTY_TREE, changed_files)

    return GitContext(
        repo_name=root.name,
        branch=branch,
        head_sha=head_sha,
        changed_files=changed_files[:MAX_CHANGED_FILES],
        recent_commits=recent_commits,
        diff=diff,
        diff_truncated=truncated,
    )


def _changed_files(root: Path) -> list[ChangedFile]:
    out = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    entries = out.split("\0")
    files: list[ChangedFile] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if xy[0] in "RC":
            i += 1  # -z puts the original path of a rename/copy in the next entry
        if _in_excluded_dir(path):
            continue
        status = "??" if xy == "??" else xy.strip()[:1]
        files.append(ChangedFile(path=path, status=status))
    return files


def _bounded_diff(root: Path, base: str, changed_files: list[ChangedFile]) -> tuple[str, bool]:
    omitted: list[str] = []

    # 1. Decide which tracked files get their diff included, using line counts.
    numstat = _git(root, "diff", base, "--numstat", "-z", "--no-renames").stdout
    include: list[str] = []
    for entry in numstat.split("\0"):
        parts = entry.split("\t", 2)
        if len(parts) != 3:
            continue
        added, deleted, path = parts
        if _in_excluded_dir(path):
            continue
        if is_excluded(path):
            omitted.append(f"{path} (excluded)")
        elif added == "-":
            omitted.append(f"{path} (binary)")
        elif int(added) + int(deleted) > MAX_FILE_LINES_CHANGED:
            omitted.append(f"{path} ({int(added) + int(deleted)} lines changed)")
        else:
            include.append(path)

    sections: list[str] = []
    if include:
        raw = _git(
            root, "diff", base, "--no-color", "--no-ext-diff", "--no-renames", "-U3",
            "--", *include[:MAX_CHANGED_FILES],
        ).stdout
        sections = ["diff --git " + s for s in raw.split("diff --git ") if s.strip()]

    # 2. Untracked files are invisible to git diff; add a few small text files.
    added_untracked = 0
    for f in changed_files:
        if f.status != "??":
            continue
        if is_excluded(f.path):
            omitted.append(f"{f.path} (excluded)")
            continue
        if added_untracked >= MAX_UNTRACKED_FILES:
            omitted.append(f"{f.path} (untracked, over file limit)")
            continue
        section = _untracked_section(root, f.path)
        if section is None:
            omitted.append(f"{f.path} (untracked, binary or too large)")
            continue
        if section.count("\n+") > MAX_FILE_LINES_CHANGED:
            omitted.append(f"{f.path} (untracked, over {MAX_FILE_LINES_CHANGED} lines)")
            continue
        sections.append(section)
        added_untracked += 1

    # 3. Sanitize and cap the total size, cutting at file boundaries.
    out: list[str] = []
    total = 0
    truncated = False
    for section in sections:
        section = sanitize(section)
        if total + len(section) > MAX_DIFF_CHARS:
            truncated = True
            if not out:  # a single huge section: keep its head
                out.append(section[:MAX_DIFF_CHARS] + "\n[... truncated]\n")
            break
        out.append(section)
        total += len(section)

    diff = "".join(out)
    if truncated:
        diff += "\n[diff truncated: size limit reached]\n"
    if omitted:
        notes = omitted[:MAX_OMITTED_NOTES]
        if len(omitted) > MAX_OMITTED_NOTES:
            notes.append(f"... and {len(omitted) - MAX_OMITTED_NOTES} more")
        diff += "\n[omitted from diff]\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    return diff, truncated


def _untracked_section(root: Path, rel_path: str) -> str | None:
    full = root / rel_path
    if full.is_symlink() or not full.is_file():
        return None
    if not full.resolve().is_relative_to(root):
        return None
    if full.stat().st_size > MAX_UNTRACKED_BYTES:
        return None
    data = full.read_bytes()
    if b"\0" in data:
        return None
    body = "".join(f"+{line}\n" for line in data.decode("utf-8", errors="replace").splitlines())
    return f"diff --git a/{rel_path} b/{rel_path}\nnew file (untracked)\n--- /dev/null\n+++ b/{rel_path}\n{body}"
