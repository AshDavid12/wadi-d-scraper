from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_LOADED = False


def load_env() -> None:
    global _LOADED
    if _LOADED:
        return
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env.local")
    load_dotenv(root / ".env")
    _LOADED = True


def require_database_url() -> str:
    load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL is not set. Add it to .env.local (Neon) or .env — see .env.example."
        )
    return url
