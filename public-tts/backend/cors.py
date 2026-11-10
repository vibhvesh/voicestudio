"""CORS headers for the public page and for https://bowlinger.net."""

from __future__ import annotations

from . import config


def allow_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    cleaned = origin.strip().rstrip("/")
    if cleaned in config.CORS_ORIGINS:
        return origin.strip()
    return None


def headers_for(origin: str | None) -> list[tuple[str, str]]:
    allowed = allow_origin(origin)
    out = [
        ("Vary", "Origin"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type, Accept"),
        ("Access-Control-Expose-Headers", (
            "Content-Disposition, X-Audio-Id, X-Target-Duration, "
            "X-Word-Count, X-WPM, X-Voice, X-Language, X-Capped-Duration"
        )),
        ("Access-Control-Max-Age", "600"),
    ]
    if allowed:
        out.insert(0, ("Access-Control-Allow-Origin", allowed))
    return out
