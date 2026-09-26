from fastapi import FastAPI

from . import config

app = FastAPI(title="Resume")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "gemini_configured": bool(config.GEMINI_API_KEY),
        "model": config.GEMINI_MODEL,
    }
