"""Validate and store the operator catalogue in the env file."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .catalog import BY_KEY, RESTART_KEYS, SECRET_KEYS, SETTINGS
from .envfile import env_path, read_env, writable, write_env

router = APIRouter()


class SettingChange(BaseModel):
    key: str
    value: str = ""


class SettingsBody(BaseModel):
    changes: list[SettingChange] = Field(default_factory=list)


def _validate(key: str, value: str) -> str:
    spec = BY_KEY[key]
    value = value.strip()
    kind = spec["kind"]
    if kind == "port":
        if not value.isdigit() or not 1 <= int(value) <= 65535:
            raise HTTPException(status_code=422, detail=f"{spec['label']} must be a port from 1 to 65535.")
    elif kind == "enum":
        options = spec.get("options") or []
        if value not in options:
            raise HTTPException(status_code=422, detail=f"{spec['label']} must be one of: {', '.join(options) or 'empty'}.")
    elif kind == "url" and value:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=422, detail=f"{spec['label']} must be an http(s) URL.")
    elif kind == "path" and value:
        if not value.startswith("/"):
            raise HTTPException(status_code=422, detail=f"{spec['label']} must be an absolute path.")
    elif kind == "text" and any(ch in value for ch in "\n\r"):
        raise HTTPException(status_code=422, detail=f"{spec['label']} must be a single line.")
    return value


def _view(stored: dict[str, str]) -> list[dict]:
    rows = []
    for spec in SETTINGS:
        key = spec["key"]
        raw = stored.get(key, "")
        secret = key in SECRET_KEYS
        live = os.environ.get(key, "")
        rows.append({
            **spec,
            "value": "" if secret else raw,
            "configured": bool(raw) if secret else True,
            "restart_required": key in RESTART_KEYS and raw != live and (raw or live),
        })
    return rows


@router.get("/settings")
def settings_get():
    stored = read_env()
    rows = _view(stored)
    return {
        "path": str(env_path()),
        "writable": writable(),
        "restart_required": any(row["restart_required"] for row in rows),
        "settings": rows,
    }


@router.put("/settings")
def settings_put(body: SettingsBody):
    if not body.changes:
        raise HTTPException(status_code=422, detail="No changes were sent.")
    if not writable():
        raise HTTPException(
            status_code=403,
            detail=f"Cannot write {env_path()}. It must be group-writable by the service user.",
        )
    updates: dict[str, str] = {}
    for change in body.changes:
        if change.key not in BY_KEY:
            raise HTTPException(status_code=422, detail=f"Unknown setting: {change.key}")
        if change.key in SECRET_KEYS and change.value.strip() in {"", "********"}:
            continue
        updates[change.key] = _validate(change.key, change.value)
    if not updates:
        return settings_get()
    try:
        write_env(updates)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    for key, value in updates.items():
        # Ports and paths keep the old process environment so the panel can
        # say a restart is still required. Secrets apply immediately.
        if key not in RESTART_KEYS:
            os.environ[key] = value
    return settings_get()
