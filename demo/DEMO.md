# Resume — judging demo

## The 30-second pitch

> Maya was hardening her API's header sanitizer when she had to leave for class. Before closing her
> laptop she saves a Resume checkpoint: one sentence and the failing test output. Two days later she
> clicks Resume. It tells her that her own middleware is dropping the auth header, what she'd already
> changed, and the exact next step — and one click opens VS Code on the buggy line.

**The bug (for us, not the judges):** `app/middleware.py` was changed to also drop `Proxy-Authorization`
using a substring check, `b"authorization" in name.lower()`, which also drops the normal
`Authorization` header. `GET /me` then returns 401 "Missing Authorization header" and `tests/test_me.py` fails.

## Setup (once, before judging)

1. Reset the demo repo (safe to run any time; it only rebuilds `~/resume-demo/buggy-api`):
   ```bash
   scripts/reset_demo.sh
   ```
   It prints the exact commands for the next steps.
2. **Terminal 1 — backend, with the separate demo database:**
   ```bash
   cd backend && RESUME_DB_PATH="$HOME/resume-demo/resume-demo.db" .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
3. **Terminal 2 — frontend:**
   ```bash
   cd frontend && npm run dev
   ```
4. Open http://localhost:5173.
5. **Create one backup checkpoint** using the inputs below, open it, and click **Open ↗** once.
   In Chrome's "Open Visual Studio Code?" prompt, tick **Always allow**.

## Checkpoint inputs

- **Repository:** `~/resume-demo/buggy-api` expanded, e.g. `/Users/<you>/resume-demo/buggy-api`
  (the form remembers it after the first save)
- **Note:**
  ```
  Hardening the header sanitizer to drop proxy auth headers before they reach the app. Now GET /me returns 401 'Missing Authorization header' even though the test sends one. Was about to check whether it survives the middleware.
  ```
- **Terminal output:** copy it with
  ```bash
  pbcopy < demo/terminal.txt
  ```
  (real `pytest` output from the buggy repo; it points at `tests/test_me.py:14`)
- **Link:** `https://fastapi.tiangolo.com/tutorial/middleware/`

## Live demo (60–90 seconds)

1. *(optional, 5s)* In `~/resume-demo/buggy-api`, run `pytest` to show it failing.
2. **Resume → New checkpoint.** The repo path is prefilled; it shows `✓ buggy-api · main · 1 changed file`.
3. Paste the note, terminal output, and link. **Save.** While it spins (~5–10s):
   *"Gemini is reading the diff, the error, and the note."*
4. **Restore screen:** point at the big **NEXT STEP**, then what was tried, the error, and the files.
5. Click **Open ↗** on `app/middleware.py` → VS Code opens **on the buggy line** (from the diff).
6. Click **Open ↗** on `tests/test_me.py` → VS Code opens at **line 14**, the failing assertion (from the terminal output).
7. *(optional)* Refresh the page: the checkpoint is still there (SQLite).

## Fallback

- **Save shows "AI summary unavailable"** (Gemini rate-limited or down): the checkpoint is still saved with a
  basic summary. Say *"AI is infrastructure — Resume never loses your work"*, then go back to the dashboard and
  open the **backup checkpoint** from setup.
- **"Could not reach the Resume backend"**: Terminal 1 isn't running. Note that Docker on this Mac also
  listens on port 8000; our backend binds `127.0.0.1:8000` and takes precedence only while it is running.
- **Open ↗ does nothing**: allow the Chrome prompt; make sure VS Code is installed.

## Between judges

```bash
scripts/reset_demo.sh
```

This restores the repo to the identical starting state (same commit IDs). Saved checkpoints stay in
`~/resume-demo/resume-demo.db`, and their Open links keep working because the path is unchanged.
