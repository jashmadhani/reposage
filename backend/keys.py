"""Rotate between several Gemini API keys.

Free-tier quota is per Google project, so keys only help when they come from
different projects. Put them in .env as GEMINI_API_KEYS=key1,key2,key3 (a single
GEMINI_API_KEY or GOOGLE_API_KEY still works). When a request fails with a quota
error, the next key is used and the failed request is retried.
"""

import os
import time

COOLDOWN_SECONDS = 3600  # a key that hit its quota is skipped for this long

_exhausted: dict[str, float] = {}
_active: str | None = None


def all_keys() -> list[str]:
    raw = [os.getenv("GEMINI_API_KEYS", ""), os.getenv("GEMINI_API_KEY", ""), os.getenv("GOOGLE_API_KEY", "")]
    keys = []
    for chunk in raw:
        for k in chunk.split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
    return keys


def _available() -> list[str]:
    now = time.time()
    return [k for k in all_keys() if _exhausted.get(k, 0) <= now]


def activate() -> bool:
    """Point the Google client libraries at the first usable key. Returns False
    if every key is cooling down or none is set."""
    global _active
    usable = _available()
    if not usable:
        return False
    if _active not in usable:
        _active = usable[0]
    os.environ["GOOGLE_API_KEY"] = _active
    return True


def is_quota_error(error: Exception) -> bool:
    text = str(error)
    return "RESOURCE_EXHAUSTED" in text or "429" in text[:200]


def rotate_after_quota_error() -> bool:
    """Mark the active key as used up and switch to another. False if none left."""
    global _active
    if _active:
        _exhausted[_active] = time.time() + COOLDOWN_SECONDS
    _active = None
    return activate()


def reset() -> None:
    global _active
    _exhausted.clear()
    _active = None
