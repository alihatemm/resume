#!/usr/bin/env bash
# Rebuilds the judging demo repo (~/resume-demo/buggy-api) in exactly the same state every time:
# two commits with fixed authors/dates, plus one uncommitted change (the bug) in app/middleware.py.
#
# It only ever deletes a directory that this script created (marked by .git/resume-demo).
# It never touches the Resume source repo or the demo database (~/resume-demo/resume-demo.db).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SRC="$REPO_ROOT/demo/buggy-api"
DEMO_HOME="$HOME/resume-demo"
TARGET="$DEMO_HOME/buggy-api"
DEMO_DB="$DEMO_HOME/resume-demo.db"
MARKER=".git/resume-demo"

die() { echo "reset_demo: $*" >&2; exit 1; }

# ---------- safety checks before anything is deleted ----------
[ -n "${HOME:-}" ] && [ "$HOME" != "/" ] || die "HOME is not set sensibly."
[ -d "$SRC/base" ] && [ -d "$SRC/stage2" ] && [ -d "$SRC/wip" ] || die "demo source layers not found in $SRC"
mkdir -p "$DEMO_HOME"
DEMO_HOME_REAL="$(cd "$DEMO_HOME" && pwd -P)"
case "$DEMO_HOME_REAL/" in
  "$REPO_ROOT"/*) die "refusing: $DEMO_HOME is inside the Resume repo." ;;
esac

if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
  [ -d "$TARGET" ] && [ ! -L "$TARGET" ] || die "refusing: $TARGET exists but is not a plain directory."
  [ -f "$TARGET/$MARKER" ] || die "refusing: $TARGET exists but was not created by this script (no $MARKER). Move it away first."
  rm -rf -- "$TARGET"
fi

# ---------- build ----------
mkdir "$TARGET"
cd "$TARGET"

g() {
  git -c core.hooksPath=/dev/null -c commit.gpgsign=false -c init.defaultBranch=main "$@"
}
commit() {  # commit <iso date> <message>
  GIT_AUTHOR_DATE="$1" GIT_COMMITTER_DATE="$1" g commit -q --no-verify -m "$2"
}

g init -q -b main
git config user.name "Maya Chen"
git config user.email "maya@example.com"
git config commit.gpgsign false
export GIT_AUTHOR_NAME="Maya Chen" GIT_AUTHOR_EMAIL="maya@example.com"
export GIT_COMMITTER_NAME="Maya Chen" GIT_COMMITTER_EMAIL="maya@example.com"
: > "$MARKER"

cp -R "$SRC/base/." .
g add -A
commit "2026-09-24T14:05:00-04:00" "Add /me endpoint with bearer auth"

cp -R "$SRC/stage2/." .
g add -A
commit "2026-09-25T16:40:00-04:00" "Add header sanitizer middleware"

cp -R "$SRC/wip/." .   # work in progress: left uncommitted on purpose

# ---------- self-checks ----------
STATUS="$(git status --porcelain --untracked-files=all)"
[ "$STATUS" = " M app/middleware.py" ] || die "unexpected git status:
$STATUS"
grep -q 'assert response.status_code == 200, response.json()' <(sed -n 14p tests/test_me.py) \
  || die "tests/test_me.py line 14 changed; demo/terminal.txt no longer matches the code."
grep -q '^tests/test_me.py:14: in test_me_returns_current_user$' "$REPO_ROOT/demo/terminal.txt" \
  || die "demo/terminal.txt does not reference tests/test_me.py:14."

HEAD_SHA="$(git rev-parse --short HEAD)"

# ---------- next steps ----------
cat <<EOF

Demo repo reset: $TARGET
  branch main @ $HEAD_SHA, 2 commits, 1 uncommitted change (app/middleware.py)
  demo database (untouched): $DEMO_DB

Next steps (copy exactly):

  # Terminal 1 - Resume backend, using the separate demo database
  cd "$REPO_ROOT/backend" && RESUME_DB_PATH="$DEMO_DB" .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

  # Terminal 2 - Resume frontend
  cd "$REPO_ROOT/frontend" && npm run dev

  # Browser
  open http://localhost:5173

  # New checkpoint form
  Repository:  $TARGET
  Note:        Hardening the header sanitizer to drop proxy auth headers before they reach the app. Now GET /me returns 401 'Missing Authorization header' even though the test sends one. Was about to check whether it survives the middleware.
  Terminal:    pbcopy < "$REPO_ROOT/demo/terminal.txt"    (then paste)
  Link:        https://fastapi.tiangolo.com/tutorial/middleware/

Full script and fallback plan: $REPO_ROOT/demo/DEMO.md
EOF
