"""Restart, stop, and update through the root-owned service helper.

The app tree is owned by the service user, so the helper lives outside it.
sudo is limited to that one program and the four verbs below.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

HELPER = Path(os.environ.get(
    "VOICESTUDIO_SERVICE_CONTROL",
    "/usr/local/lib/voicestudio/service-control.sh",
))
VERBS = ("status", "restart", "stop", "update")


def run(verb: str, timeout: float = 20) -> dict:
    if verb not in VERBS:
        return {"ok": False, "detail": f"Unknown action: {verb}"}
    if not HELPER.is_file():
        return {
            "ok": False,
            "detail": (
                f"{HELPER} is not installed. On the host run "
                f"sudo bash scripts/install.sh again, or systemctl restart "
                "voicestudio-api voicestudio-web."
            ),
        }
    command = [str(HELPER), verb]
    if os.geteuid() != 0:
        command = ["sudo", "-n", *command]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": f"{verb} timed out"}
    except OSError as exc:
        return {"ok": False, "detail": str(exc)}
    output = (completed.stdout or "") + (completed.stderr or "")
    return {
        "ok": completed.returncode == 0,
        "code": completed.returncode,
        "output": output[-8000:],
        "detail": "" if completed.returncode == 0 else output[-2000:] or f"exit {completed.returncode}",
    }
