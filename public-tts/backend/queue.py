"""Single in-flight generation job so the CPU host is not overloaded."""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_busy_since: float | None = None


def try_acquire() -> bool:
    global _busy_since
    with _lock:
        if _busy_since is not None:
            return False
        _busy_since = time.time()
        return True


def release() -> None:
    global _busy_since
    with _lock:
        _busy_since = None


def busy_for_s() -> float | None:
    with _lock:
        if _busy_since is None:
            return None
        return max(0.0, time.time() - _busy_since)


def is_busy() -> bool:
    return busy_for_s() is not None
