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


def _default_entry() -> dict:
    return {
        "used": 0,
        "paid_photos": 0,
        "created_at": time.time(),
        "subscription": None,
        "sub_photo_limit": 0,
        "sub_used": 0,
        "sub_period_start": 0,
        "stripe_subscription_id": None,
    }


def get_usage(session_id: str) -> dict:
    data = _load()
    if session_id not in data:
        data[session_id] = _default_entry()
        _save(data)
    entry = data[session_id]
    # Backfill missing fields for old entries
    for key, val in _default_entry().items():
        if key not in entry:
            entry[key] = val
    return entry


def increment_usage(session_id: str):
    data = _load()
    entry = data.get(session_id, _default_entry())
    entry["used"] += 1
    if entry.get("subscription") and _is_sub_active(entry):
        entry["sub_used"] = entry.get("sub_used", 0) + 1
    data[session_id] = entry
    _save(data)


def add_paid_photos(session_id: str, count: int):
    data = _load()
    entry = data.get(session_id, _default_entry())
    entry["paid_photos"] += count
    data[session_id] = entry
    _save(data)


def set_subscription(session_id: str, plan: str, photo_limit: int, stripe_sub_id: str):
    """Activate or update a subscription for a session."""
    data = _load()
    entry = data.get(session_id, _default_entry())
    entry["subscription"] = plan
    entry["sub_photo_limit"] = photo_limit
    entry["sub_used"] = 0
    entry["sub_period_start"] = time.time()
    entry["stripe_subscription_id"] = stripe_sub_id
    data[session_id] = entry
    _save(data)


def cancel_subscription(session_id: str):
    """Cancel subscription for a session."""
    data = _load()
    entry = data.get(session_id, _default_entry())
    entry["subscription"] = None
    entry["stripe_subscription_id"] = None
    data[session_id] = entry
    _save(data)


def reset_subscription_period(session_id: str):
    """Reset monthly usage counter (called on subscription renewal)."""
    data = _load()
    entry = data.get(session_id, _default_entry())
    entry["sub_used"] = 0
    entry["sub_period_start"] = time.time()
    data[session_id] = entry
    _save(data)


def _is_sub_active(entry: dict) -> bool:
    """Check if the subscription period is still active (within ~31 days)."""
    if not entry.get("subscription"):
        return False
    elapsed = time.time() - entry.get("sub_period_start", 0)
    return elapsed < 31 * 24 * 3600


def get_remaining(session_id: str, free_limit: int) -> int:
    usage = get_usage(session_id)
    # Base: free + paid packs
    total_allowed = free_limit + usage.get("paid_photos", 0)
    base_remaining = max(0, total_allowed - usage["used"])

    # Active subscription adds its own pool
    if _is_sub_active(usage):
        sub_limit = usage.get("sub_photo_limit", 0)
        sub_used = usage.get("sub_used", 0)
        if sub_limit == 0:
            # Unlimited plan
            return 999999
        return base_remaining + max(0, sub_limit - sub_used)

    return base_remaining
