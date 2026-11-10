"""Optional transcripts for training clips. Uses on-server ASR when present."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

log = logging.getLogger("voicestudio.voice_training")


def transcribe_clip(path: Union[str, Path], *, language: Optional[str] = None) -> Optional[str]:
    """Return a transcript when a recognizer is available, otherwise None.

    Failures are swallowed so training can continue with a hand-edited transcript.
    """
    try:
        from services.asr_backend import transcribe_reference
    except Exception as exc:  # noqa: BLE001
        log.info("No transcriber available (%s).", exc)
        return None
    try:
        text = transcribe_reference(str(path))
    except Exception as exc:  # noqa: BLE001
        log.info("Auto-transcript failed for %s (%s).", Path(path).name, exc)
        return None
    if not text:
        return None
    cleaned = " ".join(str(text).split())
    return cleaned or None
