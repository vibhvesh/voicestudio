"""Time-stretch WAV audio with ffmpeg atempo, without changing pitch."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .wpm import atempo_filter

LOG = logging.getLogger("voicestudio-speak")


class TempoError(RuntimeError):
    pass


def stretch(audio: bytes, factor: float) -> bytes:
    """Return audio stretched by ``factor`` (values < 1 slow the speech down)."""
    if factor <= 0:
        raise TempoError("atempo factor must be positive")
    if abs(factor - 1.0) < 0.001:
        return audio
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise TempoError("ffmpeg is not installed; cannot apply a slower speaking rate.")
    filt = atempo_filter(factor)
    with tempfile.TemporaryDirectory(prefix="vs-tempo-") as tmp:
        src = Path(tmp) / "in.wav"
        dst = Path(tmp) / "out.wav"
        src.write_bytes(audio)
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-filter:a", filt,
            "-c:a", "pcm_s16le",
            str(dst),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
        except subprocess.TimeoutExpired as exc:
            raise TempoError("ffmpeg atempo timed out.") from exc
        if proc.returncode != 0 or not dst.is_file() or dst.stat().st_size < 64:
            err = (proc.stderr or b"").decode("utf-8", "replace")[:400]
            LOG.warning("ffmpeg atempo failed: %s", err)
            raise TempoError(err or "ffmpeg atempo failed.")
        return dst.read_bytes()
