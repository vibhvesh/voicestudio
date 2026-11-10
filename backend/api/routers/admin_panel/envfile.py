"""Read and write the VPS env file without shelling out to it.

Values are single-line KEY=VALUE pairs. Secrets are never returned by the
settings catalogue; callers pass them back only when the operator typed a
new value.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

_KEY = re.compile(r"^[A-Z][A-Z0-9_]*$")


def env_path() -> Path:
    configured = os.environ.get("VOICESTUDIO_ENV_FILE", "").strip()
    if configured:
        return Path(configured)
    default = Path("/etc/voicestudio/voicestudio.env")
    if default.is_file():
        return default
    data = os.environ.get("OMNIVOICE_DATA_DIR", "").strip()
    if data:
        return Path(data) / "admin.env"
    return default


def read_env(path: Path | None = None) -> dict[str, str]:
    target = path or env_path()
    values: dict[str, str] = {}
    if not target.is_file():
        return values
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if _KEY.match(key):
            values[key] = value
    return values


def write_env(updates: dict[str, str], path: Path | None = None) -> Path:
    target = path or env_path()
    for key, value in updates.items():
        if not _KEY.match(key):
            raise ValueError(f"Invalid setting name: {key}")
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} cannot contain a newline")
    current = read_env(target)
    current.update(updates)
    body = "".join(f"{key}={current[key]}\n" for key in sorted(current))
    # The env file is often group-writable while its directory is not, so a
    # temp file next to it cannot be created. Rewrite the file in place.
    if target.is_file() and os.access(target, os.W_OK):
        with target.open("w", encoding="utf-8") as handle:
            handle.write(body)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".env.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        os.chmod(tmp_name, 0o660)
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return target


def writable(path: Path | None = None) -> bool:
    target = path or env_path()
    if target.is_file():
        return os.access(target, os.W_OK)
    return os.access(target.parent, os.W_OK) if target.parent.exists() else False
