"""Storage usage, cleanup of generated audio, and a config export."""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from core.config import DATA_DIR, OUTPUTS_DIR

from .catalog import SECRET_KEYS
from .envfile import read_env

router = APIRouter()


def _dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


def _usage() -> dict:
    data = Path(DATA_DIR)
    outputs = Path(OUTPUTS_DIR)
    hf = Path(os.environ.get("HF_HOME", "")) if os.environ.get("HF_HOME") else None
    db = data / "omnivoice.db"
    return {
        "data_dir": str(data),
        "data_bytes": _dir_size(data),
        "outputs_dir": str(outputs),
        "outputs_bytes": _dir_size(outputs),
        "database_bytes": db.stat().st_size if db.is_file() else 0,
        "models_dir": str(hf) if hf else "",
        "models_bytes": _dir_size(hf) if hf and hf.exists() else 0,
    }


@router.get("/data")
def data_usage():
    return _usage()


class CleanupBody(BaseModel):
    older_than_days: int = 0
    confirm: bool = False


@router.post("/data/cleanup")
def data_cleanup(body: CleanupBody):
    if not body.confirm:
        raise HTTPException(status_code=422, detail="Set confirm to delete generated audio.")
    if body.older_than_days < 0:
        raise HTTPException(status_code=422, detail="Days cannot be negative.")
    cutoff = time.time() - body.older_than_days * 86400 if body.older_than_days else None
    removed = 0
    freed = 0
    root = Path(OUTPUTS_DIR)
    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if cutoff is not None and stat.st_mtime > cutoff:
                continue
            try:
                path.unlink()
            except OSError:
                continue
            removed += 1
            freed += stat.st_size
    return {"removed": removed, "freed_bytes": freed, **_usage()}


@router.get("/data/export")
def data_export(include_secrets: bool = False):
    stored = read_env()
    lines = [
        "# VoiceStudio config export",
        "# Secrets are omitted unless include_secrets=true.",
    ]
    for key in sorted(stored):
        value = stored[key]
        if key in SECRET_KEYS or key == "OMNIVOICE_API_KEY":
            if not include_secrets:
                lines.append(f"{key}=")
                continue
        lines.append(f"{key}={value}")
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")
