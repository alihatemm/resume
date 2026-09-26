# Resume

**Pick up exactly where you left off.**

Resume captures your developer context (git changes, errors, notes, a quick voice thought) before you step away, and restores it — with one-click jumps back into VS Code — when you return.

Built for ShellHacks 2026. Runs locally on purpose: it needs access to your git repos and VS Code.

## Setup on a new Mac (once, ~10 minutes)

### 1. Install prerequisites

You need **git**, **Python 3.12**, and **Node 22+**. Check what you already have:

```bash
git --version
python3.12 --version
node --version        # must be v22.12+ (or v20.19+)
```

Install anything missing with [Homebrew](https://brew.sh):

```bash
# Homebrew itself (skip if `brew --version` works). Follow the "Next steps" it prints
# to add brew to your PATH, then open a new terminal.
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install git python@3.12 node
```

> Don't use the macOS built-in `python3` (3.9) — it's too old for our dependencies.

### 2. Clone the repo

```bash
cd ~/Desktop            # or wherever you keep projects
git clone https://github.com/alihatemm/resume.git
cd resume
```

All commands below assume you start in this `resume/` folder.

### 3. Create your own `.env` with your own Gemini key

1. Get a free key at <https://aistudio.google.com> → **Get API key** → **Create API key**. Use your **own** key; don't share keys.
2. Create your local `.env` from the template:
   ```bash
   cp .env.example .env
   open -e .env          # or: code .env
   ```
3. Replace `your-key-here` with your key and save. It should look like this (no quotes, no spaces around `=`):
   ```
   GEMINI_API_KEY=AIza...your key...
   GEMINI_MODEL=gemini-3.8-flash
   ```
4. Confirm git ignores it — this must print `.env`:
   ```bash
   git check-ignore .env
   ```

**Never commit `.env` or paste your key into chat, Slack, or code.**

### 4. Install backend dependencies

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Verify your key and model work:

```bash
.venv/bin/python -m app.check_gemini
```

Expected: a list of flash models, then a last line like `parsed: ok=True message='...'`.

### 5. Install frontend dependencies

```bash
cd ../frontend
npm install
```

## Run (two terminals)

```bash
# terminal 1 — API on http://127.0.0.1:8000
cd backend
.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# terminal 2 — UI (proxies /api to the backend)
cd frontend
npm run dev
```

Open **<http://localhost:5173>** (use `localhost`, not `127.0.0.1`). You should see the Resume page showing `backend: ok`, `gemini key: configured`, and `model: gemini-3.8-flash`.

Stop either server with `Ctrl+C`.

## Daily workflow

```bash
git pull
cd backend && .venv/bin/pip install -r requirements.txt   # only if requirements.txt changed
cd ../frontend && npm install                              # only if package.json changed
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `python3.12: command not found` | `brew install python@3.12`, then open a new terminal. |
| `check_gemini` says `GEMINI_API_KEY is missing` | `.env` must be in the repo root (next to `.env.example`), not in `backend/`. |
| `404 NOT_FOUND ... model ... no longer available` | Set `GEMINI_MODEL=gemini-3.8-flash` in `.env`. |
| `400/403 API key not valid` | Re-copy the key from AI Studio into `.env`; no quotes or spaces. |
| Page says **Backend unreachable** | Terminal 1 isn't running, or crashed — check its output. |
| `Address already in use` | Something is on that port: `lsof -i :8000` (or `:5173`), then `kill <PID>`. |
| Vite errors about Node version | `brew upgrade node` (need v22.12+ or v20.19+). |

## Layout

- `backend/app/schemas.py` — the shared data contract (mirrored in `frontend/src/types.ts`)
- `backend/app/` — FastAPI app, git capture, Gemini calls, SQLite
- `frontend/src/` — React + Tailwind UI
- `demo/`, `scripts/` — demo repo template and reset script
