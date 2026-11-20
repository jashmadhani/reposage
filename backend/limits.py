"""In-memory sliding window limiter, one deque of timestamps per (ip, bucket)."""

import time
from collections import defaultdict, deque

WINDOW_SECONDS = 3600
LIMITS = {"ask": 60, "index": 10}

_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def check(
    ip: str, bucket: str, max_per_hour: int, now: float | None = None, window: int = WINDOW_SECONDS
) -> bool:
    """Record a hit and return True if allowed, False if over the limit in `window` seconds."""
    now = time.time() if now is None else now
    q = _hits[(ip, bucket)]
    while q and q[0] <= now - window:
        q.popleft()
    if len(q) >= max_per_hour:
        return False
    q.append(now)
    return True


def reset() -> None:
    _hits.clear()
