# VoiceStudio Speak

A simple public page for the VoiceStudio (OmniVoice) install: type text, pick a language, set words per minute, then play or download the speech.

The browser talks only to this proxy. The VoiceStudio API key is read from `/etc/voicestudio/voicestudio.env` on the server and is never sent to the client.

## Endpoints

Root `/api/*` is the primary surface (https://bowlinger.net/voice/api/* is proxied here). An optional `/speak` alias serves the same routes.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` or `/speak/` | The page |
| GET | `/api/health` | Liveness and queue size |
| GET | `/api/meta` | Limits, voices, baseline WPM |
| GET | `/api/languages` | OmniVoice language catalog |
| POST | `/api/jobs` | Start a narration; returns `{job_id, position}` at once (HTTP 202) |
| GET | `/api/jobs/{id}` | Status: `queued`, `running`, `done`, or `error`, plus position and elapsed time |
| GET | `/api/jobs/{id}/audio` | The WAV when `done` |
| POST | `/api/generate` | Compatibility: waits and returns the audio in one request |

The frontend always builds URLs as `apiBase + "/api/..."`, including the audio fetch.

## Words per minute

A baseline of about **194 WPM** was measured on this host at `speed=1.0`. SOP tests found that `duration` and `speed < 1` do not reliably slow the words.

- Faster than 194 WPM: native `speed = target / 194`
- Slower than 194 WPM: generate at `speed=1.0`, then ffmpeg `atempo = target / 194`

## Run

```bash
python3 backend/app.py
```

Listens on `0.0.0.0:8788` by default and forwards generation to `http://127.0.0.1:3900`.

Abuse protection: 500-character cap, 5 narrations per IP per hour, 20 per hour globally, a single worker, and finished jobs expire after 30 minutes.

## Hosting on https://bowlinger.net/voice/

The PA bot serves the static bundle at `/voice/` with `js/config.js` `apiBase: "/voice"`, and proxies `/voice/api/*` to `http://130.250.191.136:8788/api/*`. Leave root `/api/*` on the VPS unchanged. Generation can take several minutes, so the proxy read timeout must be long enough for status polls; the job itself is not tied to a single HTTP request.
