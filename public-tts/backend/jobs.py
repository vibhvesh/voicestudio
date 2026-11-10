"""Async generation jobs: one worker, in-memory store, 30-minute expiry."""

from __future__ import annotations

import logging
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional
import io
import wave

from . import config, proxy, tempo, wpm

LOG = logging.getLogger("voicestudio-speak")


def _audio_duration(data: bytes) -> float | None:
    if not data or not data.startswith(b"RIFF"):
        return None
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            rate = wf.getframerate()
            if rate <= 0:
                return None
            return wf.getnframes() / float(rate)
    except Exception:
        return None


STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"


@dataclass
class Job:
    job_id: str
    text: str
    language: str
    voice_id: str
    wpm_value: float
    plan: wpm.RatePlan
    reference_bytes: Optional[bytes] = None
    reference_name: Optional[str] = None
    status: str = STATUS_QUEUED
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    audio: Optional[bytes] = None
    content_type: str = "audio/wav"
    meta: dict[str, Any] = field(default_factory=dict)
    done: threading.Event = field(default_factory=threading.Event)

    @property
    def elapsed_s(self) -> float:
        end = self.finished_at or time.time()
        start = self.started_at or self.created_at
        return max(0.0, end - start)

    def public_dict(self, position: int = 0) -> dict[str, Any]:
        payload = {
            "job_id": self.job_id,
            "status": self.status,
            "position": position if self.status == STATUS_QUEUED else 0,
            "elapsed_s": round(self.elapsed_s, 1),
            "error": self.error,
            "word_count": self.plan.words,
            "wpm": self.wpm_value,
            "language": self.language,
            "voice": self.voice_id,
            "target_duration_s": self.plan.expected_duration_s,
            "method": self.plan.method,
            "capped": self.plan.capped,
        }
        if self.status == STATUS_DONE:
            payload["audio_path"] = f"/api/jobs/{self.job_id}/audio"
            payload["content_type"] = self.content_type
            if self.meta.get("audio_duration_s") is not None:
                payload["audio_duration_s"] = self.meta["audio_duration_s"]
        return payload


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._queue: deque[str] = deque()
        self._cv = threading.Condition(self._lock)
        self._worker_started = False

    def start(self) -> None:
        with self._lock:
            if self._worker_started:
                return
            self._worker_started = True
            thread = threading.Thread(target=self._worker, name="voicestudio-speak-worker", daemon=True)
            thread.start()

    def submit(self, job: Job) -> tuple[Job, int]:
        self.expire()
        with self._cv:
            if len(self._queue) >= config.MAX_QUEUE:
                raise QueueFull("The narration queue is full. Please try again in a moment.")
            self._jobs[job.job_id] = job
            self._queue.append(job.job_id)
            position = self._position_unlocked(job.job_id)
            self._cv.notify()
            return job, position

    def get(self, job_id: str) -> Optional[Job]:
        self.expire()
        with self._lock:
            return self._jobs.get(job_id)

    def position(self, job_id: str) -> int:
        with self._lock:
            return self._position_unlocked(job_id)

    def _position_unlocked(self, job_id: str) -> int:
        try:
            return list(self._queue).index(job_id) + 1
        except ValueError:
            return 0

    def wait(self, job_id: str, timeout: float) -> Optional[Job]:
        job = self.get(job_id)
        if job is None:
            return None
        job.done.wait(timeout=timeout)
        return self.get(job_id)

    def expire(self) -> None:
        cutoff = time.time() - config.JOB_TTL_S
        with self._lock:
            stale = [
                job_id for job_id, job in self._jobs.items()
                if job.finished_at is not None and job.finished_at < cutoff
            ]
            for job_id in stale:
                self._jobs.pop(job_id, None)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            running = any(j.status == STATUS_RUNNING for j in self._jobs.values())
            return {
                "queued": len(self._queue),
                "running": running,
                "stored": len(self._jobs),
            }

    def _worker(self) -> None:
        while True:
            with self._cv:
                while not self._queue:
                    self._cv.wait()
                job_id = self._queue.popleft()
                job = self._jobs.get(job_id)
                if job is None:
                    continue
                job.status = STATUS_RUNNING
                job.started_at = time.time()
            try:
                self._run(job)
            except Exception as exc:
                LOG.exception("job %s failed", job.job_id)
                job.status = STATUS_ERROR
                job.error = "Something went wrong while generating speech."
                job.finished_at = time.time()
                job.done.set()

    def _run(self, job: Job) -> None:
        plan = job.plan
        try:
            audio, content_type, meta = proxy.generate(
                text=job.text,
                language=job.language,
                voice_id=job.voice_id,
                speed=plan.api_speed,
                reference_bytes=job.reference_bytes,
                reference_name=job.reference_name,
            )
            if plan.method == "atempo" and plan.atempo is not None:
                audio = tempo.stretch(audio, plan.atempo)
                content_type = "audio/wav"
                meta["atempo"] = plan.atempo
                meta["atempo_filter"] = plan.atempo_filter
            job.audio = audio
            job.content_type = content_type or "audio/wav"
            meta["bytes"] = len(audio)
            duration = _audio_duration(audio)
            if duration is not None:
                meta["audio_duration_s"] = round(duration, 3)
            job.meta = meta
            job.status = STATUS_DONE
        except proxy.UpstreamError as exc:
            job.status = STATUS_ERROR
            job.error = (exc.body or "The voice engine could not generate that clip.")[:400]
            job.meta = {"upstream_status": exc.status}
        except tempo.TempoError as exc:
            job.status = STATUS_ERROR
            job.error = str(exc) or "Could not apply the speaking-rate stretch."
        except Exception:
            LOG.exception("job %s crashed", job.job_id)
            job.status = STATUS_ERROR
            job.error = "Something went wrong while generating speech."
        finally:
            job.finished_at = time.time()
            job.done.set()


class QueueFull(Exception):
    pass


def new_job_id() -> str:
    return secrets.token_urlsafe(12)


STORE = JobStore()
