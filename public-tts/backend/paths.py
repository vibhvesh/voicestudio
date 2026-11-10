"""URL helpers: root /api/* always works; /speak is an optional alias."""

from __future__ import annotations

from . import config


def logical_path(raw: str) -> str:
    """Strip the optional public prefix so /speak/api/jobs maps to /api/jobs.

    Root paths such as /api/jobs are returned unchanged. That is the surface
    https://bowlinger.net/voice/api/* is proxied to.
    """
    path = raw or "/"
    prefix = config.PUBLIC_PREFIX
    if prefix and (path == prefix or path.startswith(prefix + "/")):
        rest = path[len(prefix):]
        return rest or "/"
    return path


def prefixes() -> tuple[str, ...]:
    """Mount points that serve the same app (root and optional alias)."""
    prefix = config.PUBLIC_PREFIX
    return ("", prefix) if prefix else ("",)
