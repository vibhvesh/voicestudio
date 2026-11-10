"""Trim and lightly denoise a reference clip for a saved voice.

Recipe matches the v1 Amit clone reference: silence trim, cap at 20 s,
highpass at 80 Hz, afftdn denoise, short fades, mono 24 kHz. Clips shorter
than 10 seconds after silence trim are rejected.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

MIN_SECONDS = 10.0
MAX_SECONDS = 20.0
SAMPLE_RATE = 24000


class ProcessingError(ValueError):
    """The reference clip could not be accepted."""


def process_reference(source: Union[str, Path], dest: Optional[Union[str, Path]] = None) -> tuple[Path, float]:
    """Process ``source`` and write a mono 24 kHz WAV.

    Returns ``(output_path, duration_seconds)``.
    """
    src = Path(source)
    if not src.is_file():
        raise ProcessingError("The reference recording is missing.")
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ProcessingError("ffmpeg is required to prepare a reference clip.")

    tmpdir = Path(tempfile.mkdtemp(prefix="saved-voice-ref-"))
    try:
        mono = tmpdir / "mono.wav"
        _run([
            ffmpeg, "-y", "-i", str(src),
            "-ac", "1", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", str(mono),
        ], "Could not read the reference recording.")
        trimmed = tmpdir / "trimmed.wav"
        _run([
            ffmpeg, "-y", "-i", str(mono),
            "-af", (
                "silenceremove=start_periods=1:start_silence=0.12:start_threshold=-35dB:"
                "stop_periods=1:stop_silence=0.18:stop_threshold=-35dB"
            ),
            "-c:a", "pcm_s16le", str(trimmed),
        ], "Could not trim silence from the reference recording.")
        duration = _duration(ffprobe, trimmed)
        if duration < MIN_SECONDS:
            # If silence removal ate a usable clip (common on already-denoised
            # references), fall back to the mono decode and cap afterwards.
            trimmed = mono
            duration = _duration(ffprobe, trimmed)
        if duration < MIN_SECONDS:
            raise ProcessingError(
                f"The reference clip must be at least {MIN_SECONDS:.0f} seconds "
                f"after trimming silence (got {duration:.1f}s)."
            )
        capped = tmpdir / "capped.wav"
        if duration > MAX_SECONDS:
            _run([
                ffmpeg, "-y", "-i", str(trimmed),
                "-t", f"{MAX_SECONDS:.3f}",
                "-c:a", "pcm_s16le", str(capped),
            ], "Could not shorten the reference recording to 20 seconds.")
            duration = min(duration, MAX_SECONDS)
        else:
            capped = trimmed
        fade_out_start = max(0.0, duration - 0.08)
        cleaned = tmpdir / "cleaned.wav"
        _run([
            ffmpeg, "-y", "-i", str(capped),
            "-af", (
                f"highpass=f=80,afftdn=nr=10:nf=-25,"
                f"afade=t=in:st=0:d=0.02,afade=t=out:st={fade_out_start:.3f}:d=0.08"
            ),
            "-ac", "1", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", str(cleaned),
        ], "Could not denoise the reference recording.")
        final_duration = _duration(ffprobe, cleaned)
        if final_duration < MIN_SECONDS - 0.25:
            raise ProcessingError(
                f"The reference clip must be at least {MIN_SECONDS:.0f} seconds "
                f"(got {final_duration:.1f}s after processing)."
            )
        out = Path(dest) if dest else tmpdir.parent / f"{src.stem}-clean.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cleaned, out)
        return out, round(final_duration, 3)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _duration(ffprobe: str, path: Path) -> float:
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, capture_output=True, text=True, timeout=60,
        )
        return float((result.stdout or "0").strip())
    except (ValueError, subprocess.SubprocessError) as exc:
        raise ProcessingError("Could not measure the reference clip duration.") from exc


def _run(cmd: list[str], message: str) -> None:
    try:
        completed = subprocess.run(
            cmd, check=False, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProcessingError(message) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else ""
        raise ProcessingError(f"{message} {tail}".strip())
