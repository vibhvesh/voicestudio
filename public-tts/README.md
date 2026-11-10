# VoiceStudio Speak

A simple public page for the VoiceStudio (OmniVoice) install: type text, pick a language, set words per minute, then play or download the speech.

The browser talks only to this proxy. The VoiceStudio API key is read from `/etc/voicestudio/voicestudio.env` on the server and is never sent to the client.

## What the page offers

- Text box (500 characters) and a `.txt` file upload that fills it
- Language picker from the OmniVoice catalog (646 languages)
- Words-per-minute slider (80–220, default 150), mapped to the API `duration` parameter: `duration_s = words / wpm * 60` (capped at 45 seconds)
- Voice picker using OmniVoice design tags that the model actually accepts (gender, age, pitch, whisper)
- Optional reference-voice upload for cloning
- Progress state with an elapsed timer (this CPU host is about 11× real time)
- Audio player and download

Emotion, laughter, and “sad tone” are not separate OmniVoice controls. Write them into the text.

## Layout

```
public-tts/
  backend/          Python proxy modules
  frontend/         HTML, CSS, and JavaScript
  data/languages.tsv
  systemd/voicestudio-public.service
  tests/
```

## Run

```bash
python3 backend/app.py
```

Listens on `0.0.0.0:8788` by default and forwards generation to `http://127.0.0.1:3900`.

CORS is allowed for `https://bowlinger.net` (and www / http variants) plus the VPS origin. Set `VOICESTUDIO_PUBLIC_CORS_ORIGINS` to change that list.

Abuse protection: 500-character cap, 5 narrations per IP per hour, 20 per hour globally, and a single in-flight job.

## Hosting on bowlinger.net

This process does not configure DNS or TLS for bowlinger.net. Ship the files in `frontend/` (see the bundle README) and either:

1. Reverse-proxy `https://bowlinger.net/voice/` (or a subdomain) to `http://130.250.191.136:8788` — recommended, keeps HTTPS and avoids mixed content; or
2. Serve the static files on bowlinger.net and point `js/config.js` `apiBase` at the VPS. This only works if the page is also HTTP, or if the proxy itself is reached over HTTPS.
