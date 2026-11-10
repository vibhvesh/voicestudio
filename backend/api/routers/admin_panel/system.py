"""Health, resource gauges, service status, and logs."""

from __future__ import annotations

import os
from pathlib import Path

import psutil
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.version import APP_VERSION

from .control import run as control_run

router = APIRouter()
_LOGS = (
    Path("/var/log/voicestudio/api.log"),
    Path("/var/log/voicestudio/web.log"),
    Path("/var/log/voicestudio/update.log"),
)


def _gpu() -> dict:
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "available": True,
                "name": torch.cuda.get_device_name(0),
                "memory_bytes": int(torch.cuda.get_device_properties(0).total_memory),
            }
    except Exception:
        pass
    return {"available": False, "name": "", "memory_bytes": 0}


@router.get("/system")
def system_status():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    control = control_run("status", timeout=8)
    log_name = os.environ.get("OMNIVOICE_DATA_DIR", "")
    app_log = Path(log_name) / "omnivoice.log" if log_name else None
    return {
        "version": str(APP_VERSION),
        "health": "ok",
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "cpu_count": psutil.cpu_count() or 0,
        "memory": {
            "total_bytes": memory.total,
            "used_bytes": memory.used,
            "percent": memory.percent,
        },
        "disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": disk.percent,
        },
        "gpu": _gpu(),
        "torch_variant": os.environ.get("OMNIVOICE_TORCH_VARIANT", ""),
        "device": os.environ.get("OMNIVOICE_DEVICE", "") or "auto",
        "services": control,
        "logs": [str(path) for path in (*_LOGS, app_log) if path and path.is_file()],
    }


@router.get("/system/logs")
def system_logs(name: str = "api"):
    allowed = {
        "api": _LOGS[0],
        "web": _LOGS[1],
        "update": _LOGS[2],
    }
    data = os.environ.get("OMNIVOICE_DATA_DIR", "")
    if data:
        allowed["omnivoice.log"] = Path(data) / "omnivoice.log"
    path = allowed.get(name)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="That log is not on this machine yet.")
    text = path.read_text(encoding="utf-8", errors="replace")
    return {"name": name, "text": text[-20000:]}


class ActionBody(BaseModel):
    action: str


@router.post("/system/action")
def system_action(body: ActionBody):
    if body.action not in {"restart", "stop"}:
        raise HTTPException(status_code=422, detail="Action must be restart or stop.")
    # Restart kills this process. Return first, then ask the helper to bounce.
    import threading
    import time

    def later() -> None:
        time.sleep(0.4)
        control_run(body.action, timeout=60)

    threading.Thread(target=later, name=f"voicestudio-{body.action}", daemon=True).start()
    return {"ok": True, "detail": f"{body.action} scheduled"}
