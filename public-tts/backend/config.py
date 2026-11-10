"""Runtime settings for the public VoiceStudio Speak proxy."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = Path(os.environ.get("VOICESTUDIO_PUBLIC_FRONTEND", ROOT / "frontend"))
LANGUAGES_TSV = Path(os.environ.get("VOICESTUDIO_PUBLIC_LANGUAGES", ROOT / "data" / "languages.tsv"))

HOST = os.environ.get("VOICESTUDIO_PUBLIC_HOST", "0.0.0.0").strip() or "0.0.0.0"
PORT = int(os.environ.get("VOICESTUDIO_PUBLIC_PORT", "8788"))
API_URL = os.environ.get("VOICESTUDIO_API_URL", "http://127.0.0.1:3900").rstrip("/")

# The browser must never see this. It is only added on loopback calls.
API_KEY = os.environ.get("OMNIVOICE_API_KEY", "").strip()

MAX_TEXT_CHARS = int(os.environ.get("VOICESTUDIO_PUBLIC_MAX_CHARS", "500"))
MIN_WPM = int(os.environ.get("VOICESTUDIO_PUBLIC_MIN_WPM", "80"))
MAX_WPM = int(os.environ.get("VOICESTUDIO_PUBLIC_MAX_WPM", "220"))
DEFAULT_WPM = int(os.environ.get("VOICESTUDIO_PUBLIC_DEFAULT_WPM", "150"))
MIN_DURATION_S = float(os.environ.get("VOICESTUDIO_PUBLIC_MIN_DURATION", "1.0"))
MAX_DURATION_S = float(os.environ.get("VOICESTUDIO_PUBLIC_MAX_DURATION", "45.0"))

# On this CPU host, generation has been about 11x real time.
CPU_REALTIME_FACTOR = float(os.environ.get("VOICESTUDIO_PUBLIC_RTF", "11.0"))

RATE_LIMIT_PER_HOUR = int(os.environ.get("VOICESTUDIO_PUBLIC_RATE_PER_HOUR", "5"))
GLOBAL_JOBS_PER_HOUR = int(os.environ.get("VOICESTUDIO_PUBLIC_GLOBAL_PER_HOUR", "20"))
MAX_REFERENCE_BYTES = int(os.environ.get("VOICESTUDIO_PUBLIC_MAX_REF_BYTES", str(4 * 1024 * 1024)))
UPSTREAM_TIMEOUT_S = int(os.environ.get("VOICESTUDIO_PUBLIC_UPSTREAM_TIMEOUT", "1200"))
NUM_STEP = int(os.environ.get("VOICESTUDIO_PUBLIC_NUM_STEP", "16"))

DEFAULT_CORS_ORIGINS = (
    "https://bowlinger.net",
    "https://www.bowlinger.net",
    "http://bowlinger.net",
    "http://www.bowlinger.net",
    "http://130.250.191.136:8788",
)

def _split_origins(raw: str) -> tuple[str, ...]:
    return tuple(item.strip().rstrip("/") for item in raw.split(",") if item.strip())


CORS_ORIGINS = _split_origins(
    os.environ.get("VOICESTUDIO_PUBLIC_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
)

# Default narrator used on this server for earlier demos.
DEFAULT_VOICE = "narrator"

VOICES = {
    "narrator": {
        "id": "narrator",
        "label": "Narrator (default)",
        "instruct": "female, young adult, moderate pitch",
        "seed": 42,
        "blurb": "Young adult female, moderate pitch",
    },
    "female_young": {
        "id": "female_young",
        "label": "Female, young adult",
        "instruct": "female, young adult, moderate pitch",
        "seed": 42,
        "blurb": "Clear young adult female voice",
    },
    "male_young": {
        "id": "male_young",
        "label": "Male, young adult",
        "instruct": "male, young adult, moderate pitch",
        "seed": 7,
        "blurb": "Clear young adult male voice",
    },
    "female_middle": {
        "id": "female_middle",
        "label": "Female, middle-aged",
        "instruct": "female, middle-aged, moderate pitch",
        "seed": 11,
        "blurb": "Middle-aged female voice",
    },
    "male_middle": {
        "id": "male_middle",
        "label": "Male, middle-aged",
        "instruct": "male, middle-aged, low pitch",
        "seed": 13,
        "blurb": "Middle-aged male, lower pitch",
    },
    "child": {
        "id": "child",
        "label": "Child",
        "instruct": "female, child, high pitch",
        "seed": 17,
        "blurb": "Child voice, higher pitch",
    },
    "elderly": {
        "id": "elderly",
        "label": "Elderly",
        "instruct": "male, elderly, low pitch",
        "seed": 19,
        "blurb": "Older male, lower pitch",
    },
    "whisper": {
        "id": "whisper",
        "label": "Whisper",
        "instruct": "female, young adult, moderate pitch, whisper",
        "seed": 42,
        "blurb": "Soft whispered delivery (the only style tag this model accepts)",
    },
}

FEATURED_LANGUAGE_IDS = (
    "en", "hi", "es", "fr", "de", "ja", "zh", "yue", "arb", "pt",
    "ru", "ko", "it", "bn", "ta", "te", "mr", "gu", "pa", "ur",
    "tr", "id", "vi", "th", "nl", "pl", "uk", "sv", "el", "fa",
    "he", "sw", "kn", "ml", "as", "hu", "fi", "da", "no", "cs",
    "ro", "bg", "sr", "hr", "ca", "ne",
)

ALLOWED_REFERENCE_SUFFIXES = {".wav", ".mp3", ".ogg", ".opus", ".flac", ".m4a", ".webm", ".aac"}
