"""Sanity check for the Gemini setup. Never prints the API key.

Run from backend/:  .venv/bin/python -m app.check_gemini
"""

import sys

from google import genai
from pydantic import BaseModel

from . import config


class Ping(BaseModel):
    ok: bool
    message: str


def main() -> int:
    if not config.GEMINI_API_KEY:
        print("GEMINI_API_KEY is missing. Add it to the repo-root .env file.")
        return 1

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    print("Flash models available to this key:")
    flash = sorted(m.name.removeprefix("models/") for m in client.models.list() if "flash" in m.name)
    for name in flash:
        print(f"  {name}")

    print(f"\nTesting structured output with {config.GEMINI_MODEL} ...")
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents="Reply with ok=true and a five-word greeting for a hackathon team.",
        config={"response_mime_type": "application/json", "response_schema": Ping},
    )
    print(f"  parsed: {response.parsed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
