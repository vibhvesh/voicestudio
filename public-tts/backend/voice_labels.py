"""Short display names for public style presets.

Internal preset ids, instruct strings and seeds stay unchanged.
Only the visible label and a one-line hint are replaced.
"""

from __future__ import annotations

from typing import Any, Iterable

# Keep this order in the public list after saved clone voices.
PRESET_ORDER = (
    "narrator",
    "female_young",
    "male_young",
    "female_middle",
    "male_middle",
    "child",
    "elderly",
    "whisper",
)

# id -> (short name, tiny grey hint). "whisper" was not renamed; keep it short.
PRESET_DISPLAY = {
    "narrator": ("Priya", "young female"),
    "female_young": ("Anjali", "young female"),
    "male_young": ("Rohan", "young male"),
    "female_middle": ("Sunita", "middle-aged female"),
    "male_middle": ("Vikram", "middle-aged male"),
    "child": ("Chintu", "child"),
    "elderly": ("Dadaji", "elderly"),
    "whisper": ("Whisper", "soft whisper"),
}

LANGUAGE_HINTS = {
    "hi": "Hindi",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "zh": "Chinese",
    "ar": "Arabic",
    "arb": "Arabic",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu",
}


def decorate_presets(voices: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return style presets with short labels, in display order.

    Unknown ids (if any are added later) keep their original label and
    are appended after the named list.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for item in voices:
        if isinstance(item, dict) and item.get("id"):
            by_id[str(item["id"])] = dict(item)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for voice_id in PRESET_ORDER:
        item = by_id.get(voice_id)
        if not item:
            continue
        label, hint = PRESET_DISPLAY.get(voice_id, (item.get("label") or voice_id, ""))
        item["label"] = label
        item["blurb"] = hint
        out.append(item)
        seen.add(voice_id)
    for voice_id, item in by_id.items():
        if voice_id not in seen:
            out.append(item)
    return out


def language_hint(code: str) -> str:
    value = (code or "").strip()
    if not value:
        return "saved voice"
    return LANGUAGE_HINTS.get(value.lower(), value)
