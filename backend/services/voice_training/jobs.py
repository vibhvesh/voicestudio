
"""In-process background jobs that build a saved-voice reference profile."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .audio import (
    TrainingAudioError,
    build_reference,
    prepare_clip,
)
from .transcripts import transcribe_clip

log = logging.getLogger("voicestudio.voice_training")

WORK_ROOT = Path(os.environ.get("VOICESTUDIO_TRAINING_DIR", "/var/lib/voicestudio/voice-training"))
DEFAULT_SEED = 42
_JOBS: dict[str, "TrainingJob"] = {}
_LOCK = threading.Lock()


class TrainingJobError(ValueError):
    """The training request or job could not be accepted."""


@dataclass
class TrainingJob:
    id: str
    name: str
    language: str
    seed: int
    consent: bool
    work_dir: Path
    status: str = "queued"
    stage: str = "queued"
    progress: int = 0
    error: Optional[str] = None
    slug: Optional[str] = None
    duration_s: Optional[float] = None
    clips: list[dict[str, Any]] = field(default_factory=list)
    transcript: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "language": self.language,
            "seed": self.seed,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "error": self.error,
            "slug": self.slug,
            "duration_s": self.duration_s,
            "clips": self.clips,
            "transcript": self.transcript,
            "preview_ready": False,
        }

    def _set(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.updated_at = time.time()


def create_job(
    *,
    name: str,
    language: str,
    consent: bool,
    clips: list[tuple[str, bytes, str]],
    seed: int = DEFAULT_SEED,
) -> TrainingJob:
    """Create a job from (filename, payload, optional_transcript) clips."""
    name = (name or "").strip()
    language = (language or "").strip()
    if not name:
        raise TrainingJobError("A voice name is required.")
    if not language:
        raise TrainingJobError("A language is required.")
    if not consent:
        raise TrainingJobError("Consent is required: you must have this speaker's permission to clone their voice.")
    if not clips:
        raise TrainingJobError("Upload at least one wav, mp3, or m4a clip of the same speaker.")
    if len(clips) > 10:
        raise TrainingJobError("You can upload at most 10 clips at a time.")

    job_id = uuid.uuid4().hex[:12]
    work_dir = WORK_ROOT / "jobs" / job_id
    raw_dir = work_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    saved: list[tuple[Path, str]] = []
    for index, (filename, payload, transcript) in enumerate(clips, start=1):
        if not payload:
            raise TrainingJobError(f"Clip {index} is empty.")
        if len(payload) > 25 * 1024 * 1024:
            raise TrainingJobError(f"{filename or f'clip {index}'} is larger than 25 MB.")
        suffix = _safe_suffix(filename)
        dest = raw_dir / f"clip-{index:02d}{suffix}"
        dest.write_bytes(payload)
        saved.append((dest, (transcript or "").strip()))

    job = TrainingJob(
        id=job_id,
        name=name,
        language=language,
        seed=int(seed or DEFAULT_SEED),
        consent=True,
        work_dir=work_dir,
    )
    # Stash clip paths on the instance for the worker (not exposed in public_dict).
    job._inputs = saved  # type: ignore[attr-defined]
    with _LOCK:
        _JOBS[job.id] = job
    return job


def start_job(job_id: str) -> None:
    job = get_job(job_id)
    thread = threading.Thread(target=_run_job, args=(job,), name=f"voice-train-{job.id}", daemon=True)
    thread.start()


def get_job(job_id: str) -> TrainingJob:
    with _LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise TrainingJobError(f"Training job {job_id} was not found.")
    return job


def list_jobs() -> list[TrainingJob]:
    with _LOCK:
        return list(_JOBS.values())


def _run_job(job: TrainingJob) -> None:
    try:
        job._set(status="running", stage="Preparing clips", progress=5)
        prepared_dir = job.work_dir / "prepared"
        prepared_dir.mkdir(parents=True, exist_ok=True)
        stats = []
        transcripts: list[str] = []
        inputs: list[tuple[Path, str]] = getattr(job, "_inputs", [])
        total = max(len(inputs), 1)
        for index, (raw_path, supplied) in enumerate(inputs, start=1):
            job._set(
                stage=f"Preparing clip {index} of {total}",
                progress=5 + int(50 * (index - 1) / total),
            )
            clip = prepare_clip(raw_path, prepared_dir / f"{raw_path.stem}.wav")
            text = supplied
            if not text:
                job._set(stage=f"Transcribing clip {index} of {total}")
                text = transcribe_clip(clip.path, language=job.language) or ""
            if text:
                transcripts.append(text)
            row = clip.as_dict()
            row["transcript"] = text
            job.clips.append(row)
            stats.append(clip)

        job._set(stage="Building reference profile", progress=70)
        ref_wav = job.work_dir / "ref.wav"
        _, duration, chosen = build_reference(stats, ref_wav)
        combined_text = " ".join(t for t in transcripts if t).strip()
        if not combined_text:
            # A short placeholder keeps the clone pipeline happy if ASR is absent
            # and the user left transcripts blank; they can edit later.
            combined_text = job.name
        job.transcript = combined_text
        job.duration_s = duration
        job._set(stage="Saving voice", progress=85)

        from services.saved_voices.profiles import sync_native_profile
        from services.saved_voices.storage import upsert_voice

        voice = upsert_voice(
            name=job.name,
            language=job.language,
            seed=job.seed,
            ref_wav=ref_wav,
            ref_text=combined_text,
            duration_s=duration,
            engine="omnivoice",
            num_step=16,
            source="training",
            replace=True,
        )
        try:
            profile_id = sync_native_profile(voice)
            if profile_id and profile_id != voice.profile_id:
                voice = upsert_voice(
                    name=voice.name,
                    slug=voice.slug,
                    language=voice.language,
                    seed=voice.seed,
                    ref_wav=voice.ref_wav,
                    ref_text=voice.ref_text,
                    duration_s=voice.duration_s,
                    engine=voice.engine,
                    num_step=voice.num_step,
                    speed=voice.speed,
                    instruct=voice.instruct,
                    profile_id=profile_id,
                    source="training",
                    replace=True,
                    created_at=voice.created_at,
                )
        except Exception as exc:  # noqa: BLE001
            log.info("Native profile sync failed for %s (%s).", voice.slug, exc)

        job.slug = voice.slug
        chosen_names = [item.path.name for item in chosen]
        job._set(
            status="done",
            stage="Ready",
            progress=100,
            clips=[
                {**row, "selected": Path(row["name"]).stem in {Path(n).stem for n in chosen_names}
                 or row["name"] in chosen_names}
                for row in job.clips
            ],
        )
        log.info("Voice training finished: %s (%s, %.1fs)", voice.name, voice.slug, duration)
    except TrainingAudioError as exc:
        job._set(status="error", stage="Failed", error=str(exc))
        log.info("Voice training failed: %s", exc)
    except Exception as exc:  # noqa: BLE001
        job._set(status="error", stage="Failed", error="Training failed unexpectedly.")
        log.exception("Voice training crashed for job %s: %s", job.id, exc)


def _safe_suffix(filename: str) -> str:
    name = (filename or "").lower()
    for ext in (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"):
        if name.endswith(ext):
            return ext
    return ".bin"
