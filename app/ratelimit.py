import time
from collections import defaultdict, deque


class RateLimiter:
    """Simple in-memory limiter: max_calls per window_seconds per key."""

    def __init__(self, max_calls: int, window_seconds: float):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        q = self.calls[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.max_calls:
            return False
        q.append(now)
        return True

    def reset(self) -> None:
        self.calls.clear()
