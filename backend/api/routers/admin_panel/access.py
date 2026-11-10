"""Generate, rotate, and revoke the remote API key."""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, HTTPException

from .envfile import env_path, writable, write_env

router = APIRouter()


def _apply(value: str) -> None:
    if not writable():
        raise HTTPException(
            status_code=403,
            detail=f"Cannot write {env_path()}. Ask root to make it group-writable.",
        )
    try:
        write_env({"OMNIVOICE_API_KEY": value})
    except OSError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    os.environ["OMNIVOICE_API_KEY"] = value


@router.get("/access")
def access_state():
    current = os.environ.get("OMNIVOICE_API_KEY", "")
    return {
        "configured": bool(current.strip()),
        "preview": f"{current[:4]}…{current[-4:]}" if len(current) >= 12 else ("set" if current else ""),
        "path": str(env_path()),
        "writable": writable(),
    }


@router.post("/access/rotate")
def access_rotate():
    key = secrets.token_urlsafe(32)
    _apply(key)
    return {
        "ok": True,
        "api_key": key,
        "detail": "Previous key no longer works. Copy this key now; it is not shown again.",
    }


@router.post("/access/revoke")
def access_revoke():
    """Revoke by rotating. Clearing the key would leave the public port open."""
    key = secrets.token_urlsafe(32)
    _apply(key)
    return {
        "ok": True,
        "api_key": key,
        "detail": "The old key was revoked. A replacement was issued so remote access stays locked.",
    }
