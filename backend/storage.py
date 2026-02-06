"""Simple JSON-file storage for tracking usage per session/user."""

import json
import os
import time
from pathlib import Path

STORAGE_FILE = Path(__file__).parent / "data" / "usage.json"


def _ensure_storage():
    STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STORAGE_FILE.exists():
        STORAGE_FILE.write_text("{}")


def _load() -> dict:
    _ensure_storage()
    return json.loads(STORAGE_FILE.read_text())


def _save(data: dict):
    _ensure_storage()
    STORAGE_FILE.write_text(json.dumps(data, indent=2))


def get_usage(session_id: str) -> dict:
    data = _load()
    if session_id not in data:
        data[session_id] = {
            "used": 0,
            "paid_photos": 0,
            "created_at": time.time(),
        }
        _save(data)
    return data[session_id]


def increment_usage(session_id: str):
    data = _load()
    entry = data.get(session_id, {"used": 0, "paid_photos": 0, "created_at": time.time()})
    entry["used"] += 1
    data[session_id] = entry
    _save(data)


def add_paid_photos(session_id: str, count: int):
    data = _load()
    entry = data.get(session_id, {"used": 0, "paid_photos": 0, "created_at": time.time()})
    entry["paid_photos"] += count
    data[session_id] = entry
    _save(data)


def get_remaining(session_id: str, free_limit: int) -> int:
    usage = get_usage(session_id)
    total_allowed = free_limit + usage.get("paid_photos", 0)
    return max(0, total_allowed - usage["used"])
