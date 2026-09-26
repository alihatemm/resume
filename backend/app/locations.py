"""Server-side file locations for one-click restore (FileRef.abs_path and FileRef.line).

Computed once, when a checkpoint is created, from the verified repo root, the
allowlist, git, and the sanitized terminal text. Never from the AI. Any value
already present on an incoming FileRef is ignored and recomputed.
"""

import re
from pathlib import Path, PurePosixPath

from .git_context import EMPTY_TREE, _git, is_excluded
from .schemas import FileRef, GitContext

MAX_LINE_COUNT_BYTES = 5_000_000  # don't read huge files just to validate a line number

# @@ -old_start[,old_count] +new_start[,new_count] @@
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)
_FILE_TOKEN = r"[\w./\\~-]*\w\.[A-Za-z0-9]+"
_TERMINAL_REFS = [
    re.compile(r'File "(?P<path>[^"\n]+)", line (?P<line>\d+)'),              # Python traceback
    re.compile(rf"(?P<path>{_FILE_TOKEN})\((?P<line>\d+),\d+\)"),             # tsc: file.ts(10,5)
    re.compile(rf"(?P<path>{_FILE_TOKEN}):(?P<line>\d+)(?::\d+)?"),           # file.py:10 / file.js:10:5
]


def add_file_locations(
    root: Path,
    git: GitContext,
    files: list[FileRef],
    allowed: list[tuple[str, str]],
    terminal_text: str,
) -> list[FileRef]:
    """Returns new FileRefs with abs_path and line filled in where they can be verified."""
    root = root.resolve()
    allowed_paths = {path for path, _ in allowed}
    base = git.head_sha or EMPTY_TREE
    refs = _terminal_refs(terminal_text)

    located: list[FileRef] = []
    for f in files:
        abs_path = _safe_abs_path(root, f.path, allowed_paths)
        line = None
        if abs_path is not None:
            line = _terminal_line(f.path, abs_path, refs, allowed_paths) or _first_changed_line(root, base, f.path)
        located.append(FileRef(path=f.path, reason=f.reason, line=line, abs_path=str(abs_path) if abs_path else None))
    return located


def _safe_abs_path(root: Path, rel: str, allowed_paths: set[str]) -> Path | None:
    """The resolved absolute path for an allowlisted, existing file inside the repo, else None."""
    if rel not in allowed_paths or is_excluded(rel):
        return None
    if not rel or rel.startswith(("/", "~")) or "\\" in rel or "\0" in rel:
        return None
    if ".." in PurePosixPath(rel).parts:
        return None
    candidate = (root / rel).resolve()  # follows symlinks, so an escaping link is caught below
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def _terminal_refs(text: str) -> list[tuple[str, int]]:
    """(path token, line) pairs in the order they appear in the terminal output."""
    found = []
    for pattern in _TERMINAL_REFS:
        for m in pattern.finditer(text):
            found.append((m.start(), m.group("path"), int(m.group("line"))))
    return [(path, line) for _, path, line in sorted(found)]


def _terminal_line(rel: str, abs_path: Path, refs: list[tuple[str, int]], allowed_paths: set[str]) -> int | None:
    """The last terminal reference that maps exactly to this file and is within its line range."""
    line_count = None
    for token, line in reversed(refs):
        if not _token_matches_file(token, rel, abs_path, allowed_paths):
            continue
        if line_count is None:
            line_count = _line_count(abs_path)
        if 1 <= line <= line_count:
            return line
    return None


def _token_matches_file(token: str, rel: str, abs_path: Path, allowed_paths: set[str]) -> bool:
    token = token.strip().replace("\\", "/")
    if token.startswith("/"):
        # Absolute path: must resolve to exactly this file (not a same-named file elsewhere).
        try:
            return Path(token).resolve() == abs_path
        except (OSError, RuntimeError):
            return False
    token = token.removeprefix("./")
    if token == rel:
        return True
    if token in allowed_paths or "/" not in token:
        return False  # names a different allowed file exactly, or is a bare (possibly ambiguous) file name
    # Relative to a subdirectory of the repo (e.g. pytest run from backend/): "tests/x.py" vs "backend/tests/x.py".
    # Only if the suffix identifies exactly one allowed file; ambiguous references are not used.
    suffix_matches = [p for p in allowed_paths if p.endswith("/" + token)]
    return suffix_matches == [rel]


def _line_count(path: Path) -> int:
    try:
        if path.stat().st_size > MAX_LINE_COUNT_BYTES:
            return 0
        data = path.read_bytes()
    except OSError:
        return 0
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def _first_changed_line(root: Path, base: str, rel: str) -> int | None:
    """First added/modified line in the working-tree file, from `git diff -U0`. None for whole-new files."""
    result = _git(root, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-renames", base, "--", rel, check=False)
    if result.returncode != 0:
        return None
    m = _HUNK.search(result.stdout)
    if m is None:
        return None  # no textual diff (unchanged, untracked, or binary)
    old_start, old_count = int(m.group(1)), int(m.group(2) or 1)
    new_start, new_count = int(m.group(3)), int(m.group(4) or 1)
    if old_start == 0 and old_count == 0:
        return None  # whole file is new: "line 1" isn't useful
    if new_count == 0:
        return max(new_start, 1)  # deletion only: the line next to where code was removed
    return new_start
