from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import CACHE_DIR, CACHE_TTL_HOURS


def cache_key(home: str, away: str) -> str:
    raw = f"{home.strip().lower()}::{away.strip().lower()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def cache_path(home: str, away: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{cache_key(home, away)}.json"


def read_cached_match(home: str, away: str) -> dict[str, Any] | None:
    path = cache_path(home, away)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    created_at = datetime.fromisoformat(payload["created_at"])
    if datetime.now(timezone.utc) - created_at > timedelta(hours=CACHE_TTL_HOURS):
        return None
    return payload["data"]


def write_cached_match(home: str, away: str, data: dict[str, Any]) -> None:
    path = cache_path(home, away)
    payload = {"created_at": datetime.now(timezone.utc).isoformat(), "data": data}
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
