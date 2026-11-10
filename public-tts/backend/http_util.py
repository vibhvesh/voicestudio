"""Small HTTP helpers: JSON, multipart parsing, static files."""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

MAX_BODY = 6 * 1024 * 1024


class BodyTooLarge(ValueError):
    pass


def read_body(handler, limit: int = MAX_BODY) -> bytes:
    length = int(handler.headers.get("Content-Length") or 0)
    if length > limit:
        raise BodyTooLarge(f"Request is larger than {limit} bytes.")
    return handler.rfile.read(length) if length else b""


def parse_json(body: bytes) -> dict:
    if not body:
        return {}
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object.")
    return data


def parse_multipart(body: bytes, content_type: str) -> tuple[dict[str, str], Optional[tuple[str, bytes]]]:
    """Return (fields, file_or_none) where file is (filename, bytes)."""
    match = re.search(r"boundary=([^;]+)", content_type or "", re.I)
    if not match:
        raise ValueError("multipart request is missing a boundary.")
    boundary = match.group(1).strip().strip('"').encode("ascii", "ignore")
    if not boundary:
        raise ValueError("multipart boundary is empty.")
    parts = body.split(b"--" + boundary)
    fields: dict[str, str] = {}
    upload: Optional[tuple[str, bytes]] = None
    for raw in parts:
        chunk = raw
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        if chunk in (b"", b"--", b"--\r\n") or chunk.startswith(b"--"):
            continue
        if b"\r\n\r\n" not in chunk:
            continue
        head, rest = chunk.split(b"\r\n\r\n", 1)
        if rest.endswith(b"\r\n"):
            rest = rest[:-2]
        headers = head.decode("iso-8859-1", "replace")
        name_m = re.search(r'name="([^"]+)"', headers)
        if not name_m:
            continue
        name = name_m.group(1)
        file_m = re.search(r'filename="([^"]*)"', headers)
        if file_m:
            filename = Path(file_m.group(1)).name
            upload = (filename, rest)
        else:
            fields[name] = rest.decode("utf-8", "replace")
    return fields, upload


def safe_static(root: Path, url_path: str) -> Optional[Path]:
    path = unquote(url_path)
    if path in ("", "/"):
        path = "/index.html"
    rel = posixpath.normpath(path).lstrip("/")
    if rel.startswith(".."):
        return None
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    return None
