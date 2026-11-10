"""Forward a generation request to the loopback VoiceStudio API.

The API key is read from the server environment and is never sent to the browser.
Because the API listens on 127.0.0.1, loopback already authenticates the call;
the key is attached only as a belt-and-suspenders header.
"""

from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from . import config


class UpstreamError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(body)
        self.status = status
        self.body = body


def _headers() -> dict[str, str]:
    headers = {"Accept": "audio/wav, audio/mpeg, application/json, */*"}
    if config.API_KEY:
        headers["Authorization"] = f"Bearer {config.API_KEY}"
    return headers


def generate(
    *,
    text: str,
    language: str,
    voice_id: str,
    speed: float = 1.0,
    reference_bytes: Optional[bytes] = None,
    reference_name: Optional[str] = None,
) -> tuple[bytes, str, dict]:
    """Call the loopback API and return (audio_bytes, content_type, meta).

    Do not pass ``duration`` — it is not a reliable WPM control. For rates
    below the baseline, generate at speed 1.0 and stretch afterwards.
    """
    voice = config.VOICES.get(voice_id) or config.VOICES[config.DEFAULT_VOICE]
    if reference_bytes:
        return _generate_with_reference(
            text=text,
            language=language,
            speed=speed,
            voice=voice,
            reference_bytes=reference_bytes,
            reference_name=reference_name or "reference.wav",
        )
    return _generate_json(
        text=text,
        language=language,
        speed=speed,
        voice=voice,
    )


def _generate_json(text: str, language: str, speed: float, voice: dict) -> tuple[bytes, str, dict]:
    payload = {
        "model": "omnivoice",
        "input": text,
        "voice": "default",
        "language": language,
        "instruct": voice["instruct"],
        "seed": voice["seed"],
        "response_format": "wav",
        "speed": speed,
        "num_step": config.NUM_STEP,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.API_URL + "/v1/audio/speech",
        data=body,
        method="POST",
        headers={**_headers(), "Content-Type": "application/json"},
    )
    return _send(req, voice, language, speed)


def _generate_with_reference(
    text: str,
    language: str,
    speed: float,
    voice: dict,
    reference_bytes: bytes,
    reference_name: str,
) -> tuple[bytes, str, dict]:
    boundary = "----VoiceStudioSpeak7f3c9a"
    filename = Path(reference_name).name or "reference.wav"
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    fields = {
        "text": text,
        "language": language,
        "speed": str(speed),
        "num_step": str(config.NUM_STEP),
        "engine": "omnivoice",
        "effect_preset": "broadcast",
    }
    # A reference clip should carry the speaker identity; skip designed instruct.
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )
    chunks.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="ref_audio"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8")
    )
    chunks.append(reference_bytes)
    chunks.append(f"\r\n--{boundary}--\r\n".encode("ascii"))
    body = b"".join(chunks)
    req = urllib.request.Request(
        config.API_URL + "/generate",
        data=body,
        method="POST",
        headers={
            **_headers(),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    return _send(req, voice, language, speed, cloned=True)


def _send(req: urllib.request.Request, voice: dict, language: str, speed: float, cloned: bool = False) -> tuple[bytes, str, dict]:
    try:
        with urllib.request.urlopen(req, timeout=config.UPSTREAM_TIMEOUT_S) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "audio/wav")
            audio_id = resp.headers.get("X-Audio-Id", "")
            status = resp.status
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", "replace")[:2000]
        raise UpstreamError(exc.code, err) from exc
    except urllib.error.URLError as exc:
        raise UpstreamError(502, f"VoiceStudio API is unreachable: {exc.reason}") from exc

    if status >= 400:
        raise UpstreamError(status, data.decode("utf-8", "replace")[:2000])
    if not data or len(data) < 64:
        raise UpstreamError(502, "The API returned an empty audio response.")
    if data[:4] not in (b"RIFF", b"ID3", b"\xff\xfb", b"OggS", b"fLaC") and b"WAVE" not in data[:16]:
        # May still be valid MP3 without ID3; accept if content-type says audio.
        if not str(content_type).startswith("audio/"):
            raise UpstreamError(502, data.decode("utf-8", "replace")[:2000] or "Unexpected API response.")

    meta = {
        "audio_id": audio_id,
        "voice": voice["id"],
        "language": language,
        "speed": speed,
        "cloned": cloned,
        "bytes": len(data),
    }
    return data, content_type, meta
