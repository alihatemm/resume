"""Bearer-token auth for the API."""

from fastapi import HTTPException, Request

# Demo token store. A real app would verify a JWT or a session here.
TOKENS = {"demo-token": {"id": 42, "name": "Maya Chen"}}


def get_current_user(request: Request) -> dict:
    """Returns the user for the bearer token in the Authorization header."""
    auth = request.headers.get("authorization")
    if auth is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    user = TOKENS.get(auth.removeprefix("Bearer "))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    return user
