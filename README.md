# Resume

**Pick up exactly where you left off.**

Your computer remembers your files. Resume remembers your train of thought. Before you step away from
your code, Resume saves a checkpoint of your git state, a typed or spoken note, and your failing output. When you come
back, it tells you what you were doing, where you got stuck, and the exact next step, and one click opens
VS Code on the right line.

Built for ShellHacks 2026 for Microsoft's **"What's Missing?"** challenge. It runs locally on purpose,
because it needs your git repositories and your editor.

---

## The problem

Git remembers your code. It doesn't remember your train of thought.

Interruptions (a class, a meeting, a weekend) wipe out the most expensive part of programming: the mental
model of what you were doing, what you'd already tried, and what you were about to do next. Commit
messages come too late, stashes don't explain themselves, and a diff shows *what* changed, not *why* or
*what's next*. So you rebuild that context by rereading your own code, and that can take longer than
the fix itself.

## How it works

1. **Choose repo:** point Resume at a local git repository. It shows the branch and the number of changed files.
2. **Save checkpoint:** type a sentence about where you are, or record a short voice thought and edit the
   transcript. Optionally paste terminal output and links. Resume captures the git context automatically
   and Gemini writes a recovery plan.
3. **Resume later:** open the checkpoint and read the **NEXT STEP**. Click **Resume work ↗** and VS Code
   opens on the file and line to start from.

## Features

**Completed**

- **Checkpoints.** One form. Resume reads the repo's branch, HEAD, changed files, recent commits, and a
  size-capped diff, and stores them with your note, terminal output, and links in a local SQLite database.
- **Voice Thought Dump.** On New Checkpoint, click **Record thought** and say where you are (up to a
  minute). Gemini transcribes it into an editable **Voice thought** field that stays separate from your
  typed note. Whatever you save becomes recovery context for the summary. If the microphone is blocked
  or unavailable, or transcription fails, Resume says so and you can type instead. Leaving the page while
  recording stops the microphone and sends nothing.
- **Gemini recovery summary.** A structured plan with a title, what you were doing, where you got stuck,
  what you already tried, key errors (copied verbatim from your terminal output), the most relevant files,
  and one concrete **NEXT STEP**.
- **Exact file and line restoration.** Each relevant file gets an **Open ↗** link to
  `vscode://file/<path>:<line>`. Resume computes the path and line on the server, from your terminal
  output (e.g. `tests/test_me.py:14`) or from the first changed line in the diff. The AI never supplies them.
- **One-click Resume Work.** A single **Resume work ↗** action inside the NEXT STEP card opens the most
  relevant file on its line. If no file can be opened, the button isn't shown at all.
- **Since You Left.** On the restore screen, Resume compares the saved checkpoint with the repo today:
  new commits, a history that moved behind or diverged, a branch switch, and uncommitted files. It's
  deterministic git data, computed on request, with no AI.
- **Resilient AI step.** If Gemini is slow, rate-limited, or down, Resume tries an optional fallback model
  within a 15-second budget. If AI generation fails, the checkpoint still saves with a basic recovery
  summary built from your note and git state, clearly labeled as a fallback.

## Why Gemini is essential

A checkpoint's raw material is unstructured and scattered: a diff, a stack trace, a half-sentence note,
a spoken thought, a few commit subjects. The value of Resume is turning that into **one decision**, *what to do next*,
plus the reasoning behind it. That step needs a model that can read code, errors, and natural language
together, and without it Resume would just be a notes app with a diff attached. Gemini also turns a
spoken thought into text, so explaining where you are takes a few seconds of talking instead of typing.

Gemini is also constrained so its output is safe to act on:

- **Structured output:** Gemini returns JSON matching a fixed schema, so every field renders predictably.
- **Server-verified file targets:** Gemini interprets the context and may only name files from an
  allowlist of changed or explicitly mentioned files. File paths and line numbers are computed and
  verified by the backend, never invented by the model.
- **Evidence rules:** your own words (typed note and voice transcript) win any conflict, errors must be verbatim, and links must appear in
  the input. Captured content is treated as data, never as instructions.

## Why it fits "What's Missing?"

> Microsoft "What's Missing?" asks teams to identify something that is unnecessarily difficult,
> inaccessible, outdated, or missing, and build an AI-powered experience that helps someone do something
> they couldn't easily do before. The core experience should not simply be a chatbot/chat window.

- **What's missing:** a save state for your head. Tools preserve files and history, but getting back into
  interrupted work is still manual, slow, and unnecessarily difficult.
- **What Resume makes possible:** coming back days later and knowing, within seconds, what you were doing,
  what you already tried, and the exact next step. Then continuing from the right line in one click.
- **Not a chatbot:** there is no chat window. The experience is a structured restore screen with a
  prominent NEXT STEP, a file list, a Since You Left comparison, and a one-click action into your editor.

## Architecture

```
Browser: React + Vite UI (localhost:5173)
   │  /api  (proxied by the Vite dev server)
   ▼
FastAPI backend (127.0.0.1:8000)
   ├── git ─────── read-only: status, diff, log, rev-parse …
   ├── Gemini API ─ structured recovery summary and voice transcription (primary + optional fallback model)
   └── SQLite ──── checkpoints (backend/resume.db by default)

Restore screen ── vscode://file/<abs path>:<line> ──► VS Code opens on the exact line
```

| Layer | Stack |
|---|---|
| Frontend | React 19, Vite 8, TypeScript, Tailwind CSS 4, browser MediaRecorder for voice, oxlint |
| Backend | Python 3.12, FastAPI, uvicorn, pydantic, `google-genai` |
| Storage | SQLite (one table, JSON columns) |
| AI | Gemini API with structured JSON output for summaries and transcription (default `gemini-3.8-flash`) |
| Editor | VS Code via `vscode://file` links |

## Privacy and local-first

**What stays on your machine**

- The UI and API run locally, and the setup below binds the API to `127.0.0.1`.
- Checkpoints are stored in a local SQLite file, and git is only read, never written.
- Since You Left and file/line locations are computed locally from git, with no AI.

**What is sent to Gemini when you save a checkpoint**

- The repo name, branch, and HEAD commit.
- The list of files the AI may reference, and the last 5 commit subjects.
- Your note, your voice transcript (if you recorded one), the terminal output you pasted, and the links
  you added.
- The diff.

**What is sent to Gemini when you record a voice thought**

- The recording itself (up to a minute, capped at 5 MB) goes from the browser to the local backend,
  which forwards it to Gemini for transcription. The microphone is only requested when you click
  **Record thought**.
- The backend keeps the audio in memory for that request only: it is never written to disk, stored, or
  logged. The transcript is redacted like other text and returned to the form. It is stored in SQLite
  only if you save the checkpoint.

**Safeguards before anything is sent**

- Secret-looking files (`.env*`, `*.pem`, `*.key`, SSH keys, `credentials*`, …) are never read, and
  build/dependency folders (`node_modules`, `.venv`, `dist`, …) are skipped.
- Secret-looking strings (Google, OpenAI/Anthropic, GitHub, AWS, and Slack tokens, bearer tokens, private
  keys, and `api_key=`/`token=`/`password=`-style assignments) are replaced with `[REDACTED]`.
- The diff is capped at 30,000 characters and terminal output at the last 20,000.
- Your Gemini API key stays in your local `.env`, which is gitignored.

Resume is local-first, not offline: generating a summary requires sending the context above to the Gemini
API. Without a key, checkpoints still save with a basic, non-AI summary.

## Quick start

Tested on macOS with Chrome and VS Code. You need **git**, **Python 3.12**, and **Node 22.12+** (or 20.19+).

```bash
brew install git python@3.12 node        # skip anything you already have
git clone https://github.com/alihatemm/resume.git
cd resume
```

> Don't use the macOS built-in `python3` (3.9). It's too old for the dependencies.

**1. Add your Gemini key.** Get a free key at <https://aistudio.google.com> (**Get API key → Create API
key**), then:

```bash
cp .env.example .env
open -e .env                              # set GEMINI_API_KEY=... (no quotes, no spaces around =)
git check-ignore .env                     # must print .env
```

`.env.example` also documents optional overrides: `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`, and
`RESUME_DB_PATH`. Never commit `.env` or paste your key anywhere.

**2. Install the backend** and check that your key works:

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.check_gemini      # last line should look like: parsed: ok=True ...
```

**3. Install the frontend:**

```bash
cd ../frontend
npm install
```

**4. Run** in two terminals, starting from the repo root:

```bash
# terminal 1: API on http://127.0.0.1:8000
cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# terminal 2: UI, proxies /api to the backend
cd frontend && npm run dev
```

Open **<http://localhost:5173>** (use `localhost`, not `127.0.0.1`) and click **New checkpoint**.

**Tests and checks** (from the repo root)

```bash
(cd backend && .venv/bin/pytest)                    # backend test suite
(cd frontend && npm run build && npm run lint)      # type-check, production build, lint
```

## Judging demo

A reproducible demo lives in [`demo/DEMO.md`](demo/DEMO.md). [`scripts/reset_demo.sh`](scripts/reset_demo.sh)
rebuilds a small buggy FastAPI repo at `~/resume-demo/buggy-api` in the identical state every time, and the
demo backend uses a separate database (`~/resume-demo/resume-demo.db`), so your own checkpoints stay
untouched.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `python3.12: command not found` | `brew install python@3.12`, then open a new terminal. |
| `check_gemini` says `GEMINI_API_KEY is missing` | `.env` must be in the repo root (next to `.env.example`), not in `backend/`. |
| `404 NOT_FOUND ... model ... no longer available` | Set `GEMINI_MODEL=gemini-3.8-flash` in `.env`. |
| `400/403 API key not valid` | Re-copy the key from AI Studio into `.env`, with no quotes or spaces. |
| "Could not reach the Resume backend. Is the API server running?" | Terminal 1 isn't running or crashed. Check its output. |
| Checkpoints save with an **AI unavailable** / basic-summary label | Gemini was unreachable, rate-limited, or unconfigured. The checkpoint is still saved. Check your key with `check_gemini`. |
| "Microphone access was blocked" | Allow the microphone for `localhost:5173` from Chrome's address bar, or just type your note. |
| **Open ↗** or **Resume work ↗** does nothing | Allow Chrome's "Open Visual Studio Code?" prompt, and make sure VS Code is installed. |
| `Address already in use` | Something is on that port: `lsof -i :8000` (or `:5173`), then `kill <PID>`. |
| Vite errors about the Node version | `brew upgrade node` (you need v22.12+ or v20.19+). |

## Project layout

```
backend/app/
  main.py          FastAPI routes
  git_context.py   bounded, sanitized git capture; secret exclusion and redaction
  ai.py            Gemini summary with deadline, fallback model, and basic-summary fallback
  prompts.py       Gemini instructions and prompt builder
  locations.py     server-side file paths and line numbers for vscode:// links
  since.py         Since You Left comparison (read-only git, no AI)
  transcribe.py    Voice Thought Dump transcription via Gemini (audio in memory only)
  db.py            SQLite persistence
  schemas.py       shared data contract (mirrored in frontend/src/types.ts)
backend/tests/     pytest suite
frontend/src/
  screens/         Dashboard, New Checkpoint, Restore (checkpoint detail)
  components/      checkpoint cards, NEXT STEP card, file rows, Since You Left, voice thought, states
  api.ts           typed API client
demo/, scripts/    judging demo repo template, terminal fixture, and reset script
```

## Limitations

- **Single user, local only.** There are no accounts or authentication. Keep the API on `127.0.0.1`.
- **macOS, Chrome, and VS Code** are what we've tested. Restore links are VS Code-only.
- **AI summaries need a Gemini API key** and send the context listed above to Gemini. Without one, you get
  the basic summary.
- **Bounded capture:** diffs over 30,000 characters are truncated, and summaries list at most 4 files.
- **Since You Left is intentionally summary-level:** commit subjects and file names, not diffs.
- **No delete button** in the UI yet. The API supports deletion.
- **Voice thoughts are short and need a Gemini key:** up to a minute (5 MB) per recording, in a browser
  with MediaRecorder support (tested in Chrome). The transcript feeds the recovery summary; the Restore
  screen doesn't display it on its own.

## Future vision

Resume starts with code because git gives it rich, precise context. The idea is bigger: **a save-state
system for knowledge work.** The same checkpoint → recovery plan → one-click return loop could apply to
a paper draft, a design file, a dataset analysis, or a research session: anywhere the hardest part of
coming back is remembering what you were thinking.
