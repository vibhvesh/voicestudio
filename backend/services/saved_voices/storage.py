"""On-disk storage for saved clone voices.

Each voice lives in ``<voices_dir>/<slug>/`` with ``ref.wav``, ``ref.txt``
and ``meta.json``. Profile WAV files that already sit as flat files next to
these folders (for example ``demo0001.wav``) are left alone.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

ENV_DIR = "VOICESTUDIO_SAVED_VOICES_DIR"
PREFERRED_SLUG = "amit-agnihotri"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG_LEN = 64
META_NAME = "meta.json"
REF_WAV_NAME = "ref.wav"
REF_TXT_NAME = "ref.txt"

# Style presets, OpenAI aliases, and engine ids that must not be overwritten.
RESERVED_SLUGS = frozenset({
    "default", "narrator", "female-young", "female_young", "male-young",
    "male_young", "female-middle", "female_middle", "male-middle",
    "male_middle", "child", "elderly", "whisper", "alloy", "ash", "ballad",
    "cedar", "coral", "echo", "fable", "marin", "nova", "onyx", "sage",
    "shimmer", "verse", "omnivoice", "api", "admin", "voices", "new",
})


class SavedVoiceError(ValueError):
    """Invalid saved-voice request."""


class SavedVoiceNotFound(SavedVoiceError):
    """No folder exists for this slug."""


class SavedVoiceExists(SavedVoiceError):
    """Slug is already taken and replace was not requested."""


@dataclass(frozen=True)
class SavedVoice:
    slug: str
    name: str
    language: str
    seed: Optional[int]
    engine: str
    num_step: int
    speed: float
    instruct: Optional[str]
    profile_id: Optional[str]
    duration_s: Optional[float]
    created_at: Optional[str]
    source: str
    ref_wav: Path
    ref_text: str

    def public_dict(self) -> dict[str, Any]:
        """Safe fields for public dropdowns: never include paths or secrets."""
        blurb = f"Saved clone ({self.language})" if self.language else "Saved clone"
        return {
            "id": self.slug,
            "slug": self.slug,
            "name": self.name,
            "label": self.name,
            "language": self.language,
            "blurb": blurb,
        }

    def admin_dict(self) -> dict[str, Any]:
        """Admin list fields. Still no filesystem paths."""
        data = self.public_dict()
        data.update({
            "seed": self.seed,
            "engine": self.engine,
            "num_step": self.num_step,
            "speed": self.speed,
            "profile_id": self.profile_id,
            "duration_s": self.duration_s,
            "created_at": self.created_at,
            "source": self.source,
        })
        return data


def saved_voices_dir() -> Path:
    override = os.environ.get(ENV_DIR, "").strip()
    if override:
        return Path(override)
    from core.config import VOICES_DIR
    return Path(VOICES_DIR)


def slugify(name: str) -> str:
    text = (name or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    if not text:
        raise SavedVoiceError("The voice name must include letters or numbers.")
    return text[:MAX_SLUG_LEN]


def validate_slug(slug: str) -> str:
    value = (slug or "").strip().lower()
    if not SLUG_RE.match(value) or len(value) > MAX_SLUG_LEN:
        raise SavedVoiceError(
            "The voice id may only use lowercase letters, numbers and hyphens."
        )
    if value in RESERVED_SLUGS:
        raise SavedVoiceError(f"The id {value!r} is reserved. Choose another name.")
    return value


def _dir_for(slug: str) -> Path:
    return saved_voices_dir() / slug


def _read_meta(folder: Path) -> Optional[SavedVoice]:
    meta_path = folder / META_NAME
    wav_path = folder / REF_WAV_NAME
    txt_path = folder / REF_TXT_NAME
    if not meta_path.is_file() or not wav_path.is_file():
        return None
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    slug = raw.get("slug") or folder.name
    name = raw.get("name") or slug
    ref_text = ""
    if txt_path.is_file():
        try:
            ref_text = txt_path.read_text(encoding="utf-8")
        except OSError:
            ref_text = ""
    if not ref_text:
        ref_text = str(raw.get("ref_text") or "")
    seed = raw.get("seed")
    try:
        seed = int(seed) if seed is not None and str(seed) != "" else None
    except (TypeError, ValueError):
        seed = None
    duration = raw.get("duration_s")
    try:
        duration = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    return SavedVoice(
        slug=str(slug),
        name=str(name),
        language=str(raw.get("language") or ""),
        seed=seed,
        engine=str(raw.get("engine") or "omnivoice"),
        num_step=int(raw.get("num_step") or 16),
        speed=float(raw.get("speed") or 1.0),
        instruct=raw.get("instruct"),
        profile_id=raw.get("profile_id") or None,
        duration_s=duration,
        created_at=raw.get("created_at"),
        source=str(raw.get("source") or "admin"),
        ref_wav=wav_path,
        ref_text=ref_text,
    )


def lookup_voice(token: Optional[str]) -> Optional[SavedVoice]:
    """Find a saved voice by slug, name, or synced profile id."""
    value = (token or "").strip()
    if not value:
        return None
    try:
        return get_voice(value)
    except SavedVoiceNotFound:
        pass
    lowered = value.lower()
    for item in list_voices():
        if item.name.lower() == lowered:
            return item
        if item.profile_id and item.profile_id == value:
            return item
    return None


def list_voices() -> list[SavedVoice]:
    root = saved_voices_dir()
    if not root.is_dir():
        return []
    voices: list[SavedVoice] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        item = _read_meta(child)
        if item is not None:
            voices.append(item)
    return _sort(voices)


def list_public_voices() -> list[dict[str, Any]]:
    return [item.public_dict() for item in list_voices()]


def get_voice(slug: str) -> SavedVoice:
    value = (slug or "").strip().lower()
    item = _read_meta(_dir_for(value))
    if item is None:
        raise SavedVoiceNotFound(f"No saved voice named {value!r}.")
    return item


def upsert_voice(
    *,
    name: str,
    slug: Optional[str] = None,
    language: str,
    seed: Optional[int],
    ref_wav: Path,
    ref_text: str,
    duration_s: Optional[float] = None,
    engine: str = "omnivoice",
    num_step: int = 16,
    speed: float = 1.0,
    instruct: Optional[str] = None,
    profile_id: Optional[str] = None,
    source: str = "admin",
    replace: bool = True,
    created_at: Optional[str] = None,
) -> SavedVoice:
    name = (name or "").strip()
    if not name:
        raise SavedVoiceError("A voice needs a name.")
    slug_value = validate_slug(slug or slugify(name))
    folder = _dir_for(slug_value)
    if folder.exists() and not replace:
        raise SavedVoiceExists(f"A voice named {slug_value!r} already exists.")
    if not Path(ref_wav).is_file():
        raise SavedVoiceError("The processed reference clip is missing.")
    folder.mkdir(parents=True, exist_ok=True)
    dest_wav = folder / REF_WAV_NAME
    src = Path(ref_wav).resolve()
    if src != dest_wav.resolve():
        shutil.copyfile(src, dest_wav)
    (folder / REF_TXT_NAME).write_text(ref_text or "", encoding="utf-8")
    stamp = created_at or time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    if folder.joinpath(META_NAME).is_file() and not created_at:
        existing = _read_meta(folder)
        if existing and existing.created_at:
            stamp = existing.created_at
    meta = {
        "slug": slug_value,
        "name": name,
        "language": (language or "").strip(),
        "seed": seed,
        "engine": engine or "omnivoice",
        "num_step": int(num_step),
        "speed": float(speed),
        "instruct": instruct,
        "profile_id": profile_id,
        "duration_s": duration_s,
        "created_at": stamp,
        "source": source,
    }
    (folder / META_NAME).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return get_voice(slug_value)


def delete_voice(slug: str) -> SavedVoice:
    item = get_voice(slug)
    folder = _dir_for(item.slug)
    # Only remove the slug directory, never sibling flat profile files.
    if folder.is_dir() and folder.parent.resolve() == saved_voices_dir().resolve():
        shutil.rmtree(folder)
    return item


def _sort(voices: Iterable[SavedVoice]) -> list[SavedVoice]:
    items = list(voices)

    def key(item: SavedVoice) -> tuple[int, str]:
        preferred = 0 if item.slug == PREFERRED_SLUG else 1
        return (preferred, item.name.lower())

    return sorted(items, key=key)
