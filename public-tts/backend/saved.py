"""List and look up saved clone voices for the public Speak proxy.

Reads the on-disk folder layout written by the VoiceStudio saved-voices
module: ``<dir>/<slug>/{ref.wav, ref.txt, meta.json}``. Flat profile WAV
files that sit next to those folders are ignored. Only name, slug and
language are exposed to public callers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

PREFERRED_SLUG = "amit-agnihotri"
DEFAULT_DIR = "/var/lib/voicestudio/voices"
ENV_DIR = "VOICESTUDIO_SAVED_VOICES_DIR"


def voices_dir() -> Path:
    override = os.environ.get(ENV_DIR, "").strip()
    return Path(override or DEFAULT_DIR)


def public_list() -> list[dict[str, str]]:
    """Return public fields only: name, slug, language."""
    items = [_public_fields(item) for item in _load_all()]
    return [item for item in items if item]


def get(token: str) -> Optional[dict[str, Any]]:
    """Find a saved voice by slug or name. Includes seed for upstream calls."""
    value = (token or "").strip()
    if not value:
        return None
    lowered = value.lower()
    for item in _load_all():
        slug = str(item.get("slug") or "").lower()
        name = str(item.get("name") or "").lower()
        if lowered == slug or lowered == name:
            return item
    return None


def is_known(token: str) -> bool:
    return get(token) is not None


def _public_fields(item: dict[str, Any]) -> dict[str, str]:
    slug = str(item.get("slug") or "").strip()
    if not slug:
        return {}
    return {
        "name": str(item.get("name") or slug),
        "slug": slug,
        "language": str(item.get("language") or ""),
    }


def _load_all() -> list[dict[str, Any]]:
    root_dir = voices_dir()
    if not root_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    try:
        children = list(root_dir.iterdir())
    except OSError:
        return []
    for child in children:
        item = _read_folder(child)
        if item is not None:
            items.append(item)

    def key(item: dict[str, Any]) -> tuple[int, str]:
        slug = str(item.get("slug") or "")
        name = str(item.get("name") or slug)
        return (0 if slug == PREFERRED_SLUG else 1, name.lower())

    return sorted(items, key=key)


def _read_folder(folder: Path) -> Optional[dict[str, Any]]:
    if not folder.is_dir():
        return None
    meta_path = folder / "meta.json"
    wav_path = folder / "ref.wav"
    if not meta_path.is_file() or not wav_path.is_file():
        return None
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    slug = str(raw.get("slug") or folder.name)
    seed = raw.get("seed")
    try:
        seed = int(seed) if seed is not None and str(seed) != "" else None
    except (TypeError, ValueError):
        seed = None
    return {
        "slug": slug,
        "name": str(raw.get("name") or slug),
        "language": str(raw.get("language") or ""),
        "seed": seed,
        "ref_wav": str(wav_path),
    }
