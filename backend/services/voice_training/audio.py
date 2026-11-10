"""Prepare, score, and combine training clips into one reference WAV."""

from __future__ import annotations

import array
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Union

SAMPLE_RATE = 24000
MIN_CLIP_SECONDS = 1.0
MIN_REFERENCE_SECONDS = 6.0
MAX_REFERENCE_SECONDS = 15.0
TARGET_SECONDS = 12.0


class TrainingAudioError(ValueError):
    """A clip or the combined reference could not be prepared."""


@dataclass
class ClipStats:
    path: Path
    duration_s: float
    rms: float
    peak: float
    clip_fraction: float
    score: float
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.path.name,
            "duration_s": round(self.duration_s, 3),
            "rms": round(self.rms, 5),
            "peak": round(self.peak, 5),
            "clip_fraction": round(self.clip_fraction, 5),
            "score": round(self.score, 3),
            "notes": list(self.notes),
        }


def score_clip(*, duration_s: float, rms: float, peak: float, clip_fraction: float) -> tuple[float, list[str]]:
    """Pure scoring for a prepared mono clip. Higher is better."""
    notes: list[str] = []
    # Duration: prefer 6–15 s, allow shorter clips that will be concatenated.
    if duration_s <= 0:
        return 0.0, ["empty"]
    if duration_s < 3:
        duration_score = 0.35 * (duration_s / 3.0)
        notes.append("short")
    elif duration_s < MIN_REFERENCE_SECONDS:
        duration_score = 0.55 + 0.25 * ((duration_s - 3.0) / (MIN_REFERENCE_SECONDS - 3.0))
    elif duration_s <= MAX_REFERENCE_SECONDS:
        # Peak around 12 s.
        span = abs(duration_s - TARGET_SECONDS) / (MAX_REFERENCE_SECONDS - MIN_REFERENCE_SECONDS)
        duration_score = 1.0 - 0.15 * min(span, 1.0)
    else:
        duration_score = 0.7
        notes.append("long")

    # Loudness: mid RMS is healthy for 16-bit speech (~0.05–0.25).
    if rms < 0.005:
        loudness_score = 0.1
        notes.append("quiet")
    elif rms < 0.04:
        loudness_score = 0.4 + 0.5 * ((rms - 0.005) / 0.035)
        notes.append("soft")
    elif rms <= 0.25:
        loudness_score = 1.0
    else:
        loudness_score = 0.7
        notes.append("loud")

    # Clipping: fraction of samples near full scale.
    if clip_fraction > 0.02:
        clip_score = 0.15
        notes.append("clipped")
    elif clip_fraction > 0.005:
        clip_score = 0.55
        notes.append("near-clip")
    else:
        clip_score = 1.0
    if peak >= 0.99 and "clipped" not in notes and "near-clip" not in notes:
        notes.append("hot-peak")
        clip_score = min(clip_score, 0.8)

    score = 100.0 * (0.45 * duration_score + 0.30 * loudness_score + 0.25 * clip_score)
    return score, notes


def analyze_wav(path: Union[str, Path]) -> ClipStats:
    src = Path(path)
    with _open_mono16(src) as (nframes, samples, duration_s):
        if nframes == 0 or not samples:
            raise TrainingAudioError(f"{src.name} has no audio samples.")
        peak = max(abs(s) for s in samples) / 32768.0
        rms = math.sqrt(sum(s * s for s in samples) / nframes) / 32768.0
        clipped = sum(1 for s in samples if abs(s) >= 32700)
        clip_fraction = clipped / nframes
    score, notes = score_clip(
        duration_s=duration_s, rms=rms, peak=peak, clip_fraction=clip_fraction
    )
    return ClipStats(
        path=src,
        duration_s=duration_s,
        rms=rms,
        peak=peak,
        clip_fraction=clip_fraction,
        score=score,
        notes=notes,
    )


def prepare_clip(source: Union[str, Path], dest: Union[str, Path]) -> ClipStats:
    """Decode to mono 24 kHz, trim silence, light denoise. Short clips are kept."""
    src = Path(source)
    out = Path(dest)
    if not src.is_file():
        raise TrainingAudioError(f"Missing clip: {src.name}")
    ffmpeg = _tool("ffmpeg")
    ffprobe = _tool("ffprobe")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmpdir = Path(tempfile.mkdtemp(prefix="voice-train-clip-"))
    try:
        mono = tmpdir / "mono.wav"
        _run([
            ffmpeg, "-y", "-i", str(src),
            "-ac", "1", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", str(mono),
        ], f"Could not read {src.name}.")
        trimmed = tmpdir / "trimmed.wav"
        _run([
            ffmpeg, "-y", "-i", str(mono),
            "-af", (
                "silenceremove=start_periods=1:start_silence=0.12:start_threshold=-35dB:"
                "stop_periods=1:stop_silence=0.18:stop_threshold=-35dB"
            ),
            "-c:a", "pcm_s16le", str(trimmed),
        ], f"Could not trim silence from {src.name}.")
        duration = _duration(ffprobe, trimmed)
        if duration < MIN_CLIP_SECONDS:
            trimmed = mono
            duration = _duration(ffprobe, trimmed)
        if duration < MIN_CLIP_SECONDS:
            raise TrainingAudioError(
                f"{src.name} is too short after trimming silence ({duration:.1f}s)."
            )
        # Keep a usable window; final concat is capped later.
        window = trimmed
        if duration > MAX_REFERENCE_SECONDS + 5:
            window = tmpdir / "window.wav"
            start = max(0.0, (duration - MAX_REFERENCE_SECONDS) / 2.0)
            _run([
                ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{MAX_REFERENCE_SECONDS:.3f}",
                "-i", str(trimmed), "-c:a", "pcm_s16le", str(window),
            ], f"Could not window {src.name}.")
            duration = MAX_REFERENCE_SECONDS
        fade_out_start = max(0.0, duration - 0.08)
        cleaned = tmpdir / "cleaned.wav"
        _run([
            ffmpeg, "-y", "-i", str(window),
            "-af", (
                f"highpass=f=80,afftdn=nr=10:nf=-25,"
                f"afade=t=in:st=0:d=0.02,afade=t=out:st={fade_out_start:.3f}:d=0.08"
            ),
            "-ac", "1", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", str(cleaned),
        ], f"Could not denoise {src.name}.")
        shutil.copyfile(cleaned, out)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    stats = analyze_wav(out)
    stats.notes = list(stats.notes)
    return stats


def build_reference(clips: Iterable[ClipStats], dest: Union[str, Path]) -> tuple[Path, float, list[ClipStats]]:
    """Pick or concatenate the best clips into a 6–15 s reference."""
    ranked = sorted(clips, key=lambda c: c.score, reverse=True)
    if not ranked:
        raise TrainingAudioError("No usable clips were provided.")
    chosen: list[ClipStats] = []
    total = 0.0
    for clip in ranked:
        if total >= MIN_REFERENCE_SECONDS and total + min(clip.duration_s, 3.0) > MAX_REFERENCE_SECONDS:
            if total >= MIN_REFERENCE_SECONDS:
                break
        chosen.append(clip)
        total += clip.duration_s
        if total >= MAX_REFERENCE_SECONDS:
            break
    if total < MIN_REFERENCE_SECONDS:
        raise TrainingAudioError(
            f"Need at least {MIN_REFERENCE_SECONDS:.0f} seconds of usable speech "
            f"(got {total:.1f}s after scoring)."
        )
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = _tool("ffmpeg")
    ffprobe = _tool("ffprobe")
    tmpdir = Path(tempfile.mkdtemp(prefix="voice-train-ref-"))
    try:
        if len(chosen) == 1:
            joined = chosen[0].path
        else:
            listing = tmpdir / "concat.txt"
            listing.write_text(
                "".join(f"file '{path}'\n" for path in (c.path.resolve() for c in chosen)),
                encoding="utf-8",
            )
            joined = tmpdir / "joined.wav"
            _run([
                ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                "-c:a", "pcm_s16le", str(joined),
            ], "Could not combine the best clips.")
        duration = _duration(ffprobe, joined)
        capped = tmpdir / "capped.wav"
        if duration > MAX_REFERENCE_SECONDS:
            _run([
                ffmpeg, "-y", "-i", str(joined),
                "-t", f"{MAX_REFERENCE_SECONDS:.3f}",
                "-c:a", "pcm_s16le", str(capped),
            ], "Could not cap the reference to 15 seconds.")
            duration = MAX_REFERENCE_SECONDS
        else:
            capped = joined
        fade_out_start = max(0.0, duration - 0.08)
        _run([
            ffmpeg, "-y", "-i", str(capped),
            "-af", f"afade=t=in:st=0:d=0.02,afade=t=out:st={fade_out_start:.3f}:d=0.08",
            "-ac", "1", "-ar", str(SAMPLE_RATE),
            "-c:a", "pcm_s16le", str(dest_path),
        ], "Could not write the combined reference.")
        final = _duration(ffprobe, dest_path)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    if final < MIN_REFERENCE_SECONDS - 0.25:
        raise TrainingAudioError(
            f"The combined reference is too short ({final:.1f}s)."
        )
    return dest_path, round(final, 3), chosen


def _open_mono16(path: Path):
    import wave

    class _Closer:
        def __enter__(self):
            self.wav = wave.open(str(path), "rb")
            if self.wav.getnchannels() != 1 or self.wav.getsampwidth() != 2:
                self.wav.close()
                raise TrainingAudioError(f"{path.name} is not mono 16-bit PCM.")
            nframes = self.wav.getnframes()
            rate = self.wav.getframerate() or SAMPLE_RATE
            samples = array.array("h")
            samples.frombytes(self.wav.readframes(nframes))
            duration_s = nframes / float(rate)
            return nframes, samples, duration_s

        def __exit__(self, *exc):
            try:
                self.wav.close()
            except Exception:
                pass
            return False

    return _Closer()


def _tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise TrainingAudioError(f"{name} is required to prepare training clips.")
    return path


def _duration(ffprobe: str, path: Path) -> float:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=False,
    )
    try:
        return float((result.stdout or "").strip())
    except ValueError:
        return 0.0


def _run(cmd: list[str], message: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = detail[-1] if detail else "unknown ffmpeg error"
        raise TrainingAudioError(f"{message} {tail}")
