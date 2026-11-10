"""Current build versus origin, changelog, and a one-click update."""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter

from core.version import APP_VERSION, build_commit

from .control import run as control_run

router = APIRouter()
_lock = threading.Lock()
_state = {"running": False, "ok": None, "detail": ""}


def _prefix() -> Path:
    configured = os.environ.get("VOICESTUDIO_PREFIX", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4]


def _git(*args: str, timeout: float = 20) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(_prefix()), "-c", f"safe.directory={_prefix()}", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    text = ((completed.stdout or "") + (completed.stderr or "")).strip()
    return completed.returncode, text


def _log_path() -> Path:
    return Path("/var/log/voicestudio/update.log")


@router.get("/updates")
def updates_status():
    prefix = _prefix()
    code, head = _git("rev-parse", "HEAD")
    current_full = head.splitlines()[-1].strip() if code == 0 and head else ""
    ref = os.environ.get("VOICESTUDIO_REF", "main").strip() or "main"
    remote_code, remote = _git("ls-remote", "origin", f"refs/heads/{ref}")
    latest_full = ""
    if remote_code == 0 and remote:
        latest_full = remote.split()[0].strip()
    changelog = ""
    changelog_path = prefix / "CHANGELOG.md"
    if changelog_path.is_file():
        lines = changelog_path.read_text(encoding="utf-8", errors="replace").splitlines()
        changelog = "\n".join(lines[:80])
    log_text = ""
    log_file = _log_path()
    if log_file.is_file():
        log_text = log_file.read_text(encoding="utf-8", errors="replace")[-12000:]
    with _lock:
        job = dict(_state)
    return {
        "version": str(APP_VERSION),
        "commit": build_commit() or current_full[:12],
        "sha": current_full[:12],
        "latest_sha": latest_full[:12],
        "ref": ref,
        "update_available": bool(current_full and latest_full and current_full != latest_full),
        "remote_error": "" if remote_code == 0 else remote[-500:],
        "changelog": changelog,
        "log": log_text,
        "job": job,
    }


def _update_job() -> None:
    log_file = _log_path()
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    result = control_run("update", timeout=3600)
    try:
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(result.get("output") or result.get("detail") or "")
            handle.write("\n")
    except OSError:
        pass
    with _lock:
        _state["running"] = False
        _state["ok"] = bool(result.get("ok"))
        _state["detail"] = result.get("detail") or ""


@router.post("/updates/run")
def updates_run():
    with _lock:
        if _state["running"]:
            return {"ok": False, "detail": "An update is already running."}
        _state["running"] = True
        _state["ok"] = None
        _state["detail"] = ""
    threading.Thread(target=_update_job, name="voicestudio-update", daemon=True).start()
    return {"ok": True, "detail": "Update started. The API restarts when it finishes."}
