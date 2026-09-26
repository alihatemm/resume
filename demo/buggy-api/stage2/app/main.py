from fastapi import Depends, FastAPI

from app.auth import get_current_user
from app.middleware import HeaderSanitizerMiddleware

app = FastAPI(title="buggy-api")
app.add_middleware(HeaderSanitizerMiddleware)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "name": user["name"]}
