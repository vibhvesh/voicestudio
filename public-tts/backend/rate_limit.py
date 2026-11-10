"""Per-IP and global generation rate limits."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from . import config

_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)
_global: deque[float] = deque()


def _prune(bucket: deque[float], now: float, window: float = 3600.0) -> None:
    while bucket and now - bucket[0] > window:
        bucket.popleft()


def client_ip(headers: dict[str, str], peer: str) -> str:
    """Best-effort client IP. Prefer Cloudflare / forwarded headers when present."""
    cf = (headers.get("CF-Connecting-IP") or headers.get("Cf-Connecting-Ip") or "").strip()
    if cf and _looks_like_ip(cf):
        return cf
    forwarded = (headers.get("X-Forwarded-For") or headers.get("X-Real-IP") or "").strip()
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if _looks_like_ip(first):
            return first
    return peer or "0.0.0.0"


def _looks_like_ip(value: str) -> bool:
    if any(ch.isspace() for ch in value) or not value:
        return False
    if "." in value and all(p.isdigit() and 0 <= int(p) <= 255 for p in value.split(".") if p.isdigit() or p == ""):
        parts = value.split(".")
        return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    if ":" in value:
        return True
    return False


def check(ip: str) -> tuple[bool, str, int, int]:
    """Return (allowed, reason, retry_after_s, remaining)."""
    now = time.time()
    with _lock:
        _prune(_global, now)
        bucket = _hits[ip]
        _prune(bucket, now)
        if len(_global) >= config.GLOBAL_JOBS_PER_HOUR:
            retry = int(max(1, 3600 - (now - _global[0])))
            return False, "The public narrator is at its hourly limit. Please try later.", retry, 0
        remaining = max(0, config.RATE_LIMIT_PER_HOUR - len(bucket))
        if remaining <= 0:
            retry = int(max(1, 3600 - (now - bucket[0])))
            return False, "This connection has reached the hourly limit of %d narrations." % config.RATE_LIMIT_PER_HOUR, retry, 0
        return True, "", 0, remaining


def commit(ip: str) -> None:
    now = time.time()
    with _lock:
        _hits[ip].append(now)
        _global.append(now)
