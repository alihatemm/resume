# Resume

**Pick up exactly where you left off.**

Resume captures your developer context (git changes, errors, notes, a quick voice thought) before you step away, and restores it — with one-click jumps back into VS Code — when you return.

Built for ShellHacks 2026. Runs locally on purpose: it needs access to your git repos and VS Code.

## Setup (once)

Requires Python 3.10+ (we use 3.12) and Node 20+.

```bash
cp .env.example .env            # then put your own GEMINI_API_KEY in .env — never commit it

cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.check_gemini   # verifies your key + model

cd ../frontend
npm install
```

## Run (two terminals)

```bash
# terminal 1 — API on http://127.0.0.1:8000
cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# terminal 2 — UI on http://localhost:5173 (proxies /api to the backend)
cd frontend && npm run dev
```

## Layout

- `backend/app/schemas.py` — the shared data contract (mirrored in `frontend/src/types.ts`)
- `backend/app/` — FastAPI app, git capture, Gemini calls, SQLite
- `frontend/src/` — React + Tailwind UI
- `demo/`, `scripts/` — demo repo template and reset script
