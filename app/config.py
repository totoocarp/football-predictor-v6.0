from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
CACHE_DIR = ROOT_DIR / "cache"
FRONTEND_DIR = ROOT_DIR / "frontend"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))

ALLOWED_SOURCES = [
    "understat.com",
    "fbref.com",
    "whoscored.com",
    "fotmob.com",
    "transfermarkt.com",
    "soccerway.com",
    "flashscore.com",
    "sofascore.com",
    "worldfootball.net",
    "oddsportal.com",
    "betexplorer.com",
]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=1)
def load_variable_catalog() -> dict[str, Any]:
    return read_json(CONFIG_DIR / "stat_variables.json")


@lru_cache(maxsize=1)
def load_weights() -> dict[str, Any]:
    return read_json(CONFIG_DIR / "weights.json")
