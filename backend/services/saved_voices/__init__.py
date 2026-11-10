"""Saved clone voices stored under /var/lib/voicestudio/voices/<slug>/."""

from .processing import ProcessingError, process_reference
from .storage import (
    PREFERRED_SLUG,
    SavedVoice,
    SavedVoiceError,
    SavedVoiceExists,
    SavedVoiceNotFound,
    delete_voice,
    get_voice,
    lookup_voice,
    list_public_voices,
    list_voices,
    saved_voices_dir,
    slugify,
    upsert_voice,
)

__all__ = [
    "PREFERRED_SLUG",
    "ProcessingError",
    "SavedVoice",
    "SavedVoiceError",
    "SavedVoiceExists",
    "SavedVoiceNotFound",
    "delete_voice",
    "get_voice",
    "lookup_voice",
    "list_public_voices",
    "list_voices",
    "process_reference",
    "saved_voices_dir",
    "slugify",
    "upsert_voice",
]
