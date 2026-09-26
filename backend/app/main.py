import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import ai, config, db
from .git_context import GitError, allowed_files, capture, resolve_repo, sanitize
from .locations import add_file_locations
from .schemas import Checkpoint, CheckpointCreate, CheckpointListItem, GitContext

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")

MAX_NOTE_CHARS = 5_000
MAX_TRANSCRIPT_CHARS = 5_000
MAX_TERMINAL_CHARS = 20_000
MAX_LINKS = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    yield


app = FastAPI(title="Resume", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Always return {"detail": "<string>"} so the frontend can show it directly.
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p not in ("body", "query"))
        parts.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts)})


def _capture(path: str):
    try:
        root = resolve_repo(path)
        return root, capture(root)
    except GitError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "gemini_configured": bool(config.GEMINI_API_KEY),
        "model": config.GEMINI_MODEL,
    }


@app.get("/api/repo/inspect", response_model=GitContext)
def inspect_repo(path: str = Query(..., min_length=1)):
    _, git = _capture(path)
    return git


@app.post("/api/checkpoints", response_model=Checkpoint, status_code=201)
def create_checkpoint(body: CheckpointCreate):
    root, git = _capture(body.repo_path)

    # Sanitize BEFORE anything is stored or summarized; then bound sizes.
    note = sanitize(body.note).strip()[:MAX_NOTE_CHARS]
    transcript = sanitize(body.transcript).strip()[:MAX_TRANSCRIPT_CHARS]
    terminal_text = sanitize(body.terminal_text).strip()[-MAX_TERMINAL_CHARS:]
    links = [
        sanitize(url.strip())
        for url in body.links
        if url.strip().lower().startswith(("http://", "https://"))
    ][:MAX_LINKS]

    allowed = allowed_files(root, git, [note, terminal_text, transcript])
    summary, status = ai.summarize(git, note, terminal_text, transcript, links, allowed)
    # abs_path/line are computed server-side only, and stored so restore never needs git or AI.
    summary.files = add_file_locations(root, git, summary.files, allowed, terminal_text)
    checkpoint_id = db.insert(
        repo_path=str(root),
        status=status,
        note=note,
        terminal_text=terminal_text,
        transcript=transcript,
        git=git,
        summary=summary,
    )
    return db.get(checkpoint_id)


@app.get("/api/checkpoints", response_model=list[CheckpointListItem])
def list_checkpoints(repo_path: Optional[str] = None):
    return db.list_all(repo_path=repo_path)


@app.get("/api/checkpoints/{checkpoint_id}", response_model=Checkpoint)
def get_checkpoint(checkpoint_id: int):
    checkpoint = db.get(checkpoint_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found.")
    return checkpoint


@app.delete("/api/checkpoints/{checkpoint_id}", status_code=204)
def delete_checkpoint(checkpoint_id: int):
    if not db.delete(checkpoint_id):
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found.")
    return Response(status_code=204)
