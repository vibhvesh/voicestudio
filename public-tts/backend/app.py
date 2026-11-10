#!/usr/bin/env python3
"""VoiceStudio Speak — public page plus a key-safe generation proxy."""

from __future__ import annotations

import json
import logging
import mimetypes
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# Allow `python3 backend/app.py` from the public-tts directory or as a module.
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend import config, cors, languages, rate_limit, wpm
    from backend import http_util, jobs, paths, proxy, saved, voice_labels
else:
    from . import config, cors, languages, rate_limit, wpm
    from . import http_util, jobs, paths, proxy, saved, voice_labels

LOG = logging.getLogger("voicestudio-speak")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".tsv": "text/tab-separated-values; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
}

_JOB_RE = re.compile(r"^/api/jobs/([A-Za-z0-9_-]{8,64})$")
_JOB_AUDIO_RE = re.compile(r"^/api/jobs/([A-Za-z0-9_-]{8,64})/audio$")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "VoiceStudioSpeak/1.1"

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - " + fmt, self.address_string(), *args)

    def _origin(self) -> str | None:
        return self.headers.get("Origin")

    def _path(self) -> str:
        return paths.logical_path(urlparse(self.path).path)

    def _send(self, status: int, body: bytes, headers: list[tuple[str, str]] | None = None) -> None:
        self.send_response(status)
        for key, value in cors.headers_for(self._origin()):
            self.send_header(key, value)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in headers or []:
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict, extra: list[tuple[str, str]] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = [("Content-Type", "application/json; charset=utf-8")]
        if extra:
            headers.extend(extra)
        self._send(status, body, headers)

    def do_OPTIONS(self) -> None:
        self._send(204, b"", [])

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path = self._path()
        if path in ("/api/health", "/health"):
            stats = jobs.STORE.stats()
            self._json(200, {
                "ok": True,
                "service": "voicestudio-speak",
                "busy": stats["running"],
                "queued": stats["queued"],
                "prefix": config.PUBLIC_PREFIX or None,
            })
            return
        if path == "/api/meta":
            self._json(200, public_meta())
            return
        if path == "/api/voices":
            self._json(200, {"voices": saved.public_list()})
            return
        if path == "/api/languages":
            self._json(200, {"languages": languages.all_languages()})
            return
        audio_match = _JOB_AUDIO_RE.match(path)
        if audio_match:
            self._job_audio(audio_match.group(1))
            return
        job_match = _JOB_RE.match(path)
        if job_match:
            self._job_status(job_match.group(1))
            return
        self._serve_static(path)

    def _serve_static(self, path: str) -> None:
        if path.startswith("/api/"):
            self._json(404, {"error": "Not found.", "code": "not_found"})
            return
        found = http_util.safe_static(config.FRONTEND_DIR, path)
        if found is None:
            self._json(404, {"error": "Not found.", "code": "not_found"})
            return
        data = found.read_bytes()
        ctype = CONTENT_TYPES.get(found.suffix.lower()) or mimetypes.guess_type(str(found))[0] or "application/octet-stream"
        cache = "public, max-age=300" if found.suffix.lower() in {".css", ".js", ".svg", ".png"} else "no-store"
        self._send(200, data, [("Content-Type", ctype), ("Cache-Control", cache)])

    def do_POST(self) -> None:
        path = self._path()
        try:
            if path == "/api/jobs":
                self._create_job()
                return
            if path == "/api/generate":
                self._generate_sync()
                return
            self._json(404, {"error": "Not found.", "code": "not_found"})
        except http_util.BodyTooLarge as exc:
            self._json(413, {"error": str(exc), "code": "too_large"})
        except Exception:
            LOG.exception("post failed")
            self._json(500, {"error": "Something went wrong while generating speech.", "code": "internal"})

    def _create_job(self) -> None:
        parsed = self._validated_request()
        if parsed is None:
            return
        try:
            job, position = _enqueue(parsed)
        except jobs.QueueFull as exc:
            self._json(429, {"error": str(exc), "code": "busy"}, [("Retry-After", "30")])
            return
        self._json(202, {"job_id": job.job_id, "position": position, "status": job.status})

    def _generate_sync(self) -> None:
        """Compatibility endpoint: enqueue and wait, then return the audio."""
        parsed = self._validated_request()
        if parsed is None:
            return
        try:
            job, _position = _enqueue(parsed)
        except jobs.QueueFull as exc:
            self._json(429, {"error": str(exc), "code": "busy"}, [("Retry-After", "30")])
            return
        finished = jobs.STORE.wait(job.job_id, timeout=config.UPSTREAM_TIMEOUT_S)
        if finished is None:
            self._json(500, {"error": "The narration job disappeared before it finished.", "code": "internal"})
            return
        if finished.status != jobs.STATUS_DONE or not finished.audio:
            status = 502
            if finished.meta.get("upstream_status") in {400, 401, 403, 404, 409, 413, 422, 429}:
                status = int(finished.meta["upstream_status"])
            self._json(status, {"error": finished.error or "Generation failed.", "code": "upstream"})
            return
        self._send_audio(finished)

    def _job_status(self, job_id: str) -> None:
        job = jobs.STORE.get(job_id)
        if job is None:
            self._json(404, {"error": "Unknown or expired job.", "code": "not_found"})
            return
        self._json(200, job.public_dict(position=jobs.STORE.position(job_id)))

    def _job_audio(self, job_id: str) -> None:
        job = jobs.STORE.get(job_id)
        if job is None:
            self._json(404, {"error": "Unknown or expired job.", "code": "not_found"})
            return
        if job.status != jobs.STATUS_DONE or not job.audio:
            self._json(409, {
                "error": job.error or "This narration is not ready yet.",
                "code": "not_ready",
                "status": job.status,
            })
            return
        self._send_audio(job)

    def _send_audio(self, job: jobs.Job) -> None:
        plan = job.plan
        filename = f"voicestudio-{job.language}-{int(plan.expected_duration_s)}s.wav"
        if "mpeg" in (job.content_type or "") or "mp3" in (job.content_type or ""):
            filename = filename.replace(".wav", ".mp3")
        headers = [
            ("Content-Type", job.content_type or "audio/wav"),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
            ("X-Audio-Id", str(job.meta.get("audio_id") or "")),
            ("X-Target-Duration", str(plan.expected_duration_s)),
            ("X-Word-Count", str(plan.words)),
            ("X-WPM", str(int(job.wpm_value) if job.wpm_value == int(job.wpm_value) else job.wpm_value)),
            ("X-Voice", job.voice_id),
            ("X-Language", job.language),
            ("X-Capped-Duration", "1" if plan.capped else "0"),
            ("X-Rate-Method", plan.method),
            ("X-Job-Id", job.job_id),
        ]
        self._send(200, job.audio or b"", headers)

    def _validated_request(self) -> dict | None:
        try:
            fields, upload = self._read_request()
        except ValueError as exc:
            self._json(400, {"error": str(exc), "code": "bad_request"})
            return None

        text = (fields.get("text") or "").strip()
        language = (fields.get("language") or "en").strip()
        voice_id = (fields.get("voice") or config.DEFAULT_VOICE).strip()
        try:
            wpm_value = float(fields.get("wpm") or config.DEFAULT_WPM)
        except (TypeError, ValueError):
            self._json(400, {"error": "Words per minute must be a number.", "code": "bad_wpm"})
            return None

        if not text:
            self._json(400, {"error": "Please enter some text to narrate.", "code": "empty"})
            return None
        if len(text) > config.MAX_TEXT_CHARS:
            self._json(400, {
                "error": f"Text is limited to {config.MAX_TEXT_CHARS} characters.",
                "code": "too_long",
                "max_chars": config.MAX_TEXT_CHARS,
            })
            return None
        if wpm_value < config.MIN_WPM or wpm_value > config.MAX_WPM:
            self._json(400, {
                "error": f"Words per minute must be between {config.MIN_WPM} and {config.MAX_WPM}.",
                "code": "bad_wpm",
            })
            return None
        if not languages.is_supported(language):
            self._json(400, {"error": f"Language {language!r} is not in the OmniVoice catalog.", "code": "bad_language"})
            return None
        if voice_id not in config.VOICES and not saved.is_known(voice_id):
            self._json(400, {"error": "Unknown voice.", "code": "bad_voice"})
            return None

        reference_bytes = None
        reference_name = None
        if upload and upload[1]:
            reference_name, reference_bytes = upload
            suffix = Path(reference_name).suffix.lower()
            if suffix not in config.ALLOWED_REFERENCE_SUFFIXES:
                self._json(400, {"error": "Reference audio must be wav, mp3, ogg, flac, m4a or webm.", "code": "bad_reference"})
                return None
            if len(reference_bytes) > config.MAX_REFERENCE_BYTES:
                self._json(413, {"error": "Reference audio is too large (4 MB maximum).", "code": "too_large"})
                return None

        ip = rate_limit.client_ip({k: self.headers[k] for k in self.headers.keys()}, self.client_address[0])
        allowed, reason, retry_after, remaining = rate_limit.check(ip)
        if not allowed:
            self._json(429, {"error": reason, "code": "rate_limit"}, [("Retry-After", str(retry_after))])
            return None

        try:
            plan = wpm.plan_rate(
                text,
                wpm_value,
                baseline_wpm=config.BASELINE_WPM,
                min_s=config.MIN_DURATION_S,
                max_s=config.MAX_DURATION_S,
            )
        except ValueError as exc:
            self._json(400, {"error": str(exc), "code": "bad_request"})
            return None

        return {
            "ip": ip,
            "text": text,
            "language": language,
            "voice_id": voice_id,
            "wpm_value": wpm_value,
            "plan": plan,
            "reference_bytes": reference_bytes,
            "reference_name": reference_name,
        }

    def _read_request(self) -> tuple[dict[str, str], tuple[str, bytes] | None]:
        content_type = self.headers.get("Content-Type") or ""
        body = http_util.read_body(self)
        if content_type.startswith("application/json"):
            data = http_util.parse_json(body)
            fields = {str(k): "" if v is None else str(v) for k, v in data.items() if k != "reference"}
            return fields, None
        if content_type.startswith("multipart/form-data"):
            return http_util.parse_multipart(body, content_type)
        if content_type.startswith("application/x-www-form-urlencoded"):
            from urllib.parse import parse_qs
            parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
            return {k: (v[-1] if v else "") for k, v in parsed.items()}, None
        raise ValueError("Send JSON or multipart form data.")


def _enqueue(parsed: dict) -> tuple[jobs.Job, int]:
    job = jobs.Job(
        job_id=jobs.new_job_id(),
        text=parsed["text"],
        language=parsed["language"],
        voice_id=parsed["voice_id"],
        wpm_value=parsed["wpm_value"],
        plan=parsed["plan"],
        reference_bytes=parsed["reference_bytes"],
        reference_name=parsed["reference_name"],
    )
    created, position = jobs.STORE.submit(job)
    rate_limit.commit(parsed["ip"])
    return created, position


def public_meta() -> dict:
    return {
        "name": "CanberraAI Voice",
        "title": "CanberraAI Voice",
        "max_chars": config.MAX_TEXT_CHARS,
        "min_wpm": config.MIN_WPM,
        "max_wpm": config.MAX_WPM,
        "default_wpm": config.DEFAULT_WPM,
        "baseline_wpm": config.BASELINE_WPM,
        "min_duration_s": config.MIN_DURATION_S,
        "max_duration_s": config.MAX_DURATION_S,
        "cpu_realtime_factor": config.CPU_REALTIME_FACTOR,
        "rate_limit_per_hour": config.RATE_LIMIT_PER_HOUR,
        "default_voice": config.DEFAULT_VOICE,
        "poll_interval_ms": 2500,
        "prefix": config.PUBLIC_PREFIX or None,
        "voices": [
            {k: v[k] for k in ("id", "label", "blurb")}
            for v in voice_labels.decorate_presets(config.VOICES.values())
        ],
        "reference_upload": True,
        "reference_max_bytes": config.MAX_REFERENCE_BYTES,
        "note": (
            "On this CPU server, generation takes about 11 times the natural audio length. "
            "A 20 second clip often takes around 4 minutes. The page polls until the clip is ready, "
            "so a short Cloudflare timeout will not cut the job off."
        ),
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not config.FRONTEND_DIR.is_dir():
        raise SystemExit(f"frontend directory missing: {config.FRONTEND_DIR}")
    jobs.STORE.start()
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    LOG.info(
        "VoiceStudio Speak listening on %s:%s -> %s (frontend %s, prefix %r)",
        config.HOST,
        config.PORT,
        config.API_URL,
        config.FRONTEND_DIR,
        config.PUBLIC_PREFIX or "/",
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
