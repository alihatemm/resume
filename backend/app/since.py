"""Since you left: what changed in a checkpoint's repository after it was saved.

Deterministic, read-only git data computed on request (no AI). The stored checkpoint is
never modified. Output is bounded: counts, short commit subjects and file names, no diffs.
"""

import logging
from pathlib import Path

from .git_context import EMPTY_TREE, _changed_files, _git, _in_excluded_dir, sanitize
from .schemas import ChangedFile, Checkpoint, SinceCommit, SinceYouLeft

log = logging.getLogger("resume.since")

MAX_COMMITS = 10
MAX_FILES = 20
MAX_UNCOMMITTED_PATHS = 10
MAX_SUBJECT_CHARS = 120


def since_checkpoint(checkpoint: Checkpoint) -> SinceYouLeft:
    """Never raises: any failure becomes status="unavailable"."""
    saved = {"saved_head": checkpoint.git.head_sha, "saved_branch": checkpoint.git.branch}
    try:
        return _compare(Path(checkpoint.repo_path), **saved)
    except Exception as e:  # noqa: BLE001 - the Restore page must never break on this
        log.warning("Since-you-left failed for checkpoint %s (%s).", checkpoint.id, type(e).__name__)
        return _unavailable("git_error", "Couldn't compare with the current repository state.", **saved)


def _compare(root: Path, saved_head: str, saved_branch: str) -> SinceYouLeft:
    saved = {"saved_head": saved_head, "saved_branch": saved_branch}

    if not root.is_dir():
        return _unavailable("repo_missing", f"The repository is no longer at {root}.", **saved)
    top = _git(root, "rev-parse", "--show-toplevel", check=False)
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != root.resolve():
        return _unavailable("not_a_repo", f"{root} is no longer a git repository.", **saved)

    old = None
    if saved_head:
        resolved = _git(root, "rev-parse", "--verify", "-q", f"{saved_head}^{{commit}}", check=False)
        if resolved.returncode != 0:
            return _unavailable(
                "commit_missing", f"The commit you checkpointed at ({saved_head}) no longer exists in this repository.",
                **saved,
            )
        old = resolved.stdout.strip()

    head = _git(root, "rev-parse", "--verify", "-q", "HEAD", check=False)
    new = head.stdout.strip() if head.returncode == 0 else None
    branch_result = _git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False)
    current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "HEAD (detached)"

    uncommitted = _changed_files(root)
    common = {
        **saved,
        "current_branch": current_branch,
        "uncommitted_files": len(uncommitted),
        "uncommitted_paths": [f.path for f in uncommitted[:MAX_UNCOMMITTED_PATHS]],
    }

    if new is None:
        if old is None:
            return SinceYouLeft(status="unchanged", message="Nothing has been committed since this checkpoint.", **common)
        return _unavailable("git_error", "The current branch has no commits to compare with.", **common)

    current_head = _git(root, "rev-parse", "--short", new).stdout.strip()
    if new == old:
        return SinceYouLeft(
            status="unchanged", message="Nothing has been committed since this checkpoint.",
            current_head=current_head, **common,
        )

    commit_range = f"{old}..{new}" if old else new
    ahead = int(_git(root, "rev-list", "--count", commit_range).stdout.strip())
    behind = int(_git(root, "rev-list", "--count", f"{new}..{old}").stdout.strip()) if old else 0
    history = "linear" if behind == 0 else ("behind" if ahead == 0 else "diverged")

    commits = _commits(root, commit_range) if ahead else []
    files = _files(root, old or EMPTY_TREE, new)

    return SinceYouLeft(
        status="changed",
        message=_message(ahead, behind, len(files), saved_branch, current_branch),
        history=history,
        current_head=current_head,
        commits_ahead=ahead,
        commits_behind=behind,
        commits=commits[:MAX_COMMITS],
        commits_truncated=len(commits) > MAX_COMMITS,
        files_changed=len(files),
        files=files[:MAX_FILES],
        files_truncated=len(files) > MAX_FILES,
        **common,
    )


def _commits(root: Path, commit_range: str) -> list[SinceCommit]:
    out = _git(root, "log", f"-n{MAX_COMMITS + 1}", "--no-color", "--format=%h%x1f%s%x1f%an%x1f%aI", commit_range).stdout
    commits = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        sha, subject, author, date = parts
        subject = sanitize(subject).strip()
        if len(subject) > MAX_SUBJECT_CHARS:
            subject = subject[: MAX_SUBJECT_CHARS - 1].rstrip() + "…"
        commits.append(SinceCommit(sha=sha, subject=subject, author=sanitize(author), date=date))
    return commits


def _files(root: Path, old: str, new: str) -> list[ChangedFile]:
    out = _git(root, "diff", "--name-status", "-z", "--no-renames", old, new).stdout
    parts = out.split("\0")
    files = []
    for i in range(0, len(parts) - 1, 2):
        status, path = parts[i], parts[i + 1]
        if status and path and not _in_excluded_dir(path):
            files.append(ChangedFile(path=path, status=status[:1]))
    return files


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _message(ahead: int, behind: int, files: int, saved_branch: str, current_branch: str) -> str:
    if behind and ahead:
        text = (
            f"Repository history has diverged from this checkpoint: current HEAD is "
            f"{_plural(ahead, 'commit')} ahead and {_plural(behind, 'commit')} behind the saved checkpoint."
        )
    elif behind:
        text = f"Current HEAD is {_plural(behind, 'commit')} behind the saved checkpoint."
    elif files:
        text = f"{_plural(ahead, 'commit')} and {_plural(files, 'file')} changed since you saved this checkpoint."
    else:
        text = f"{_plural(ahead, 'commit')} since you saved this checkpoint, with no file changes."
    if current_branch != saved_branch:
        text += f" You're on {current_branch} now (checkpoint was on {saved_branch})."
    return text


def _unavailable(reason: str, message: str, **fields) -> SinceYouLeft:
    return SinceYouLeft(status="unavailable", reason=reason, message=message, **fields)
