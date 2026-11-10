#!/usr/bin/env python3
"""VoiceStudio Speak — public page plus a key-safe generation proxy."""

from __future__ import annotations

import json
import logging
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# Allow `python3 backend/app.py` from the public-tts directory or as a module.
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend import config, cors, languages, queue, rate_limit, wpm
    from backend import http_util, proxy
else:
    from . import config, cors, languages, queue, rate_limit, wpm
    from . import http_util, proxy

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


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "VoiceStudioSpeak/1.0"

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - " + fmt, self.address_string(), *args)

    def _origin(self) -> str | None:
        return self.headers.get("Origin")

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
        path = urlparse(self.path).path
        if path in ("/api/health", "/health"):
            busy = queue.busy_for_s()
            self._json(200, {
                "ok": True,
                "service": "voicestudio-speak",
                "busy": busy is not None,
                "busy_for_s": None if busy is None else round(busy, 1),
            })
            return
        if path == "/api/meta":
            self._json(200, public_meta())
            return
        if path == "/api/languages":
            self._json(200, {"languages": languages.all_languages()})
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
        path = urlparse(self.path).path
        if path != "/api/generate":
            self._json(404, {"error": "Not found.", "code": "not_found"})
            return
        try:
            self._generate()
        except http_util.BodyTooLarge as exc:
            self._json(413, {"error": str(exc), "code": "too_large"})
        except Exception:
            LOG.exception("generate failed")
            self._json(500, {"error": "Something went wrong while generating speech.", "code": "internal"})

    def _generate(self) -> None:
        try:
            fields, upload = self._read_request()
        except ValueError as exc:
            self._json(400, {"error": str(exc), "code": "bad_request"})
            return

        text = (fields.get("text") or "").strip()
        language = (fields.get("language") or "en").strip()
        voice_id = (fields.get("voice") or config.DEFAULT_VOICE).strip()
        try:
            wpm_value = float(fields.get("wpm") or config.DEFAULT_WPM)
        except (TypeError, ValueError):
            self._json(400, {"error": "Words per minute must be a number.", "code": "bad_wpm"})
            return

        if not text:
            self._json(400, {"error": "Please enter some text to narrate.", "code": "empty"})
            return
        if len(text) > config.MAX_TEXT_CHARS:
            self._json(400, {
                "error": f"Text is limited to {config.MAX_TEXT_CHARS} characters.",
                "code": "too_long",
                "max_chars": config.MAX_TEXT_CHARS,
            })
            return
        if wpm_value < config.MIN_WPM or wpm_value > config.MAX_WPM:
            self._json(400, {
                "error": f"Words per minute must be between {config.MIN_WPM} and {config.MAX_WPM}.",
                "code": "bad_wpm",
            })
            return
        if not languages.is_supported(language):
            self._json(400, {"error": f"Language {language!r} is not in the OmniVoice catalog.", "code": "bad_language"})
            return
        if voice_id not in config.VOICES:
            self._json(400, {"error": "Unknown voice.", "code": "bad_voice"})
            return

        reference_bytes = None
        reference_name = None
        if upload and upload[1]:
            reference_name, reference_bytes = upload
            suffix = Path(reference_name).suffix.lower()
            if suffix not in config.ALLOWED_REFERENCE_SUFFIXES:
                self._json(400, {"error": "Reference audio must be wav, mp3, ogg, flac, m4a or webm.", "code": "bad_reference"})
                return
            if len(reference_bytes) > config.MAX_REFERENCE_BYTES:
                self._json(413, {"error": "Reference audio is too large (4 MB maximum).", "code": "too_large"})
                return

        ip = rate_limit.client_ip({k: self.headers[k] for k in self.headers.keys()}, self.client_address[0])
        allowed, reason, retry_after, remaining = rate_limit.check(ip)
        if not allowed:
            self._json(429, {"error": reason, "code": "rate_limit"}, [("Retry-After", str(retry_after))])
            return

        if not queue.try_acquire():
            busy = queue.busy_for_s() or 0
            self._json(429, {
                "error": "Another narration is already running on this CPU server. Please wait and try again.",
                "code": "busy",
                "busy_for_s": round(busy, 1),
            }, [("Retry-After", "30")])
            return

        try:
            duration_s, words, capped = wpm.duration_from_wpm(
                text,
                wpm_value,
                min_s=config.MIN_DURATION_S,
                max_s=config.MAX_DURATION_S,
            )
            audio, content_type, meta = proxy.generate(
                text=text,
                language=language,
                duration_s=duration_s,
                voice_id=voice_id,
                reference_bytes=reference_bytes,
                reference_name=reference_name,
            )
        except ValueError as exc:
            queue.release()
            self._json(400, {"error": str(exc), "code": "bad_request"})
            return
        except proxy.UpstreamError as exc:
            queue.release()
            status = exc.status if exc.status in {400, 401, 403, 404, 409, 413, 422, 429} else 502
            message = _friendly_upstream(exc.body) or "The voice engine could not generate that clip."
            LOG.warning("upstream %s: %s", exc.status, exc.body[:400])
            self._json(status, {"error": message, "code": "upstream", "upstream_status": exc.status})
            return
        except Exception:
            queue.release()
            LOG.exception("generation crashed")
            self._json(500, {"error": "Something went wrong while generating speech.", "code": "internal"})
            return
        else:
            rate_limit.commit(ip)
            queue.release()

        filename = f"voicestudio-{language}-{int(duration_s)}s.wav"
        if "mpeg" in (content_type or "") or "mp3" in (content_type or ""):
            filename = filename.replace(".wav", ".mp3")
        headers = [
            ("Content-Type", content_type or "audio/wav"),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
            ("X-Audio-Id", meta.get("audio_id") or ""),
            ("X-Target-Duration", str(duration_s)),
            ("X-Word-Count", str(words)),
            ("X-WPM", str(int(wpm_value) if wpm_value == int(wpm_value) else wpm_value)),
            ("X-Voice", voice_id),
            ("X-Language", language),
            ("X-Capped-Duration", "1" if capped else "0"),
        ]
        self._send(200, audio, headers)

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


def _friendly_upstream(body: str) -> str:
    try:
        data = json.loads(body)
        detail = data.get("detail") or data.get("error") or data.get("message")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, dict):
            return json.dumps(detail)
    except Exception:
        pass
    text = (body or "").strip()
    return text[:400] if text and "<" not in text[:20] else ""


def public_meta() -> dict:
    return {
        "name": "VoiceStudio Speak",
        "title": "VoiceStudio – Text to Speech",
        "max_chars": config.MAX_TEXT_CHARS,
        "min_wpm": config.MIN_WPM,
        "max_wpm": config.MAX_WPM,
        "default_wpm": config.DEFAULT_WPM,
        "min_duration_s": config.MIN_DURATION_S,
        "max_duration_s": config.MAX_DURATION_S,
        "cpu_realtime_factor": config.CPU_REALTIME_FACTOR,
        "rate_limit_per_hour": config.RATE_LIMIT_PER_HOUR,
        "default_voice": config.DEFAULT_VOICE,
        "voices": [
            {k: v[k] for k in ("id", "label", "blurb")}
            for v in config.VOICES.values()
        ],
        "reference_upload": True,
        "reference_max_bytes": config.MAX_REFERENCE_BYTES,
        "note": (
            "On this CPU server, generation takes about 11 times the audio length. "
            "A 20 second clip often takes around 4 minutes."
        ),
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not config.FRONTEND_DIR.is_dir():
        raise SystemExit(f"frontend directory missing: {config.FRONTEND_DIR}")
    server = ThreadingHTTPServer((config.HOST, config.PORT), Handler)
    LOG.info(
        "VoiceStudio Speak listening on %s:%s -> %s (frontend %s)",
        config.HOST,
        config.PORT,
        config.API_URL,
        config.FRONTEND_DIR,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
