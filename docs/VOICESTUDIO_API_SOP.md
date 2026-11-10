# VoiceStudio API SOP — send text, get voice

**Audience:** developers integrating the deployed VoiceStudio (OmniVoice) service.  
**Deployment:** VPS `130.250.191.136`, VoiceStudio **0.5.7**, engine **omnivoice** (`k2-fsa/OmniVoice`) on **CPU** (6 vCPU, no GPU).  
**Tested:** 10 November 2026, Asia/Calcutta (IST, UTC+5:30). Short clips were generated on the live API. This SOP documents only what that engine actually does.

Hand this document and the `examples/` client modules to your developers. Keep the API key in an environment variable named `VOICESTUDIO_API_KEY`. Never put the real key in source, tickets, or chat.

---

## 1. What this system can and cannot do

| You want | How | Status on this deployment |
|---|---|---|
| Send text and get speech | `POST /v1/audio/speech` (JSON) or `POST /generate` (multipart) | **Supported natively** |
| Language (Hindi, English, …) | Send the text already in that language, plus `language` (for example `hi`, `en`) | **Supported natively**. The API does **not** translate. 646 languages. |
| Voice identity (gender, age, pitch, accent) | `instruct` with the fixed voice-design vocabulary, plus a `seed` | **Supported via instruct** (closed tag list, not free prose) |
| Same voice every time | Pin `seed` (this server’s narrator uses `42`) and the same `instruct` | **Supported natively** |
| Voice cloning from a recording | `ref_audio` (and optional `ref_text`) on `POST /generate`, or a saved profile id as `voice` | **Supported natively** (implemented by the engine; not re-tested in this SOP run) |
| Faster speech / higher WPM | `speed` **greater than 1.0** | **Supported natively** (tested at 1.5× and 2.0×) |
| Slower speech / lower WPM | Do **not** rely on `speed < 1` or `duration`. Time-stretch the file after generation with ffmpeg `atempo` | **Approximated (client-side)**. Native slow-down did not reliably change articulation |
| Whisper | Add `whisper` to `instruct` | **Supported via instruct** (tested; quieter, breathier take) |
| Laugh, sigh | Put `[laughter]` or `[sigh]` **in the text** | **Supported via text tags** (tested) |
| A pause | `[pause]`, `[pause 800ms]`, `[pause 1.5s]` in the text | **Supported via text tags** (tested; an 800 ms request produced about 1060 ms of silence) |
| Sad, happy, angry, “emotional” tone | — | **Not supported** on OmniVoice. `emo_text` is rejected. `instruct="sad"` is rejected. `[sad]` is read aloud as the word “sad”. |
| On-demand breath | — | **Not supported** on OmniVoice (no `[breath]` tag). `[sigh]` is the nearest tag |

OmniVoice is the only TTS engine installed and selected here. Graded emotion (`emo_text`, `emo_vector`) belongs to the optional IndexTTS2 engine, which is **not** available on this server.

---

## 2. Endpoints

| Role | Base URL | Notes |
|---|---|---|
| Public (use this from your app) | `http://130.250.191.136:8787` | Reverse proxy in front of the API. Requires the API key on all routes except `/health` and the web UI shell. |
| Loopback on the server only | `http://127.0.0.1:3900` | The API itself. No key needed from localhost. Not reachable from the internet (bound to `127.0.0.1`). |

Speech routes (same path on both bases):

| Method | Path | Body | Response |
|---|---|---|---|
| `POST` | `/v1/audio/speech` | JSON, OpenAI-compatible plus VoiceStudio extensions | Audio bytes (`mp3` by default; also `wav`, `opus`, `aac`, `flac`, `pcm`) |
| `POST` | `/generate` | `multipart/form-data` | `audio/wav` plus headers (`X-Audio-Duration`, `X-Gen-Time`, `X-Seed`, `X-Audio-Id`) |
| `GET` | `/health` | — | `{"status":"ok","device":"cpu","version":"0.5.7"}` (no key required) |
| `GET` | `/engines/tts` | — | Active engine, language list, expression caps (key required from outside) |
| `GET` | `/v1/audio/voices` | — | OpenAI alias names plus any saved profiles |
| `GET` | `/openapi.json` | — | Full schema |
| `GET` | `/generate/budget` | — | Time budgets (CPU generate ceiling is 7200 s) |

Prefer `/v1/audio/speech` for application code (JSON, format choice, OpenAI SDK compatible). Use `/generate` when you need the extra headers, a streaming preview, or to upload a reference clip for cloning.

Do not send traffic to port `43123` (unrelated service on the same host).

There is no TLS on port 8787 today. The Bearer token travels in plaintext. Use an SSH tunnel, a VPN, or add HTTPS before this is used on an untrusted network.

---

## 3. Authentication

Set the key on every **non-loopback** request:

```http
Authorization: Bearer $VOICESTUDIO_API_KEY
```

A missing or wrong key returns `401` with `{"detail":"API key required"}`. This was verified from outside the server on `GET /engines` (no key → 401; with key → 200).

Loopback calls to `127.0.0.1:3900` do not need a key. `/health` is public.

Store the key in the environment, for example:

```bash
export VOICESTUDIO_API_KEY='…'   # provided by the administrator, not in this document
```

The key is a root credential: it can also reach administration routes. Treat it like a password.

---

## 4. Procedure — text in, voice out

1. Put the API key in `VOICESTUDIO_API_KEY`.
2. Write the script **already in the target language**. The `language` field does not translate.
3. Choose a voice:
   - designed: `instruct` such as `female, young adult, moderate pitch`, and a `seed` (use `42` to match the narrator already used on this server), or
   - cloned: a saved profile id as `voice`, or `ref_audio` on `POST /generate`.
4. Add only the controls this engine honours: `language`, `speed` (for faster speech), `whisper` in `instruct`, and text tags such as `[laughter]`, `[sigh]`, `[pause 800ms]`.
5. `POST /v1/audio/speech` with `response_format` `mp3` or `wav`.
6. Set the HTTP timeout to at least **15 minutes**. On this CPU host a warm request takes about **9–14×** the length of the audio (a 4 s line takes roughly 40–60 s). A cold start can be slower.
7. Save the response body as the audio file.
8. If you need slower speech, time-stretch the file with ffmpeg `atempo` (see [§7](#7-words-per-minute)).
9. Pin the same `instruct` + `seed` for follow-up lines so the voice stays consistent.

---

## 5. Request and response format

### 5.1 `POST /v1/audio/speech`

```json
{
  "model": "omnivoice",
  "input": "Please leave the package by the door and I will collect it after lunch.",
  "voice": "default",
  "language": "en",
  "instruct": "female, young adult, moderate pitch",
  "seed": 42,
  "speed": 1.0,
  "num_step": 16,
  "response_format": "mp3"
}
```

Successful response: raw audio bytes (`Content-Type` `audio/mpeg` or `audio/wav`). Header `X-OmniVoice-Backend: 0.5.7`.

`input` is limited to **4096 characters**. `speed` is accepted in the range **0.25–4.0**.

OpenAI field names work too: `instructions` is accepted, but OmniVoice **keeps only valid voice-design tags** from it and drops the rest. If both are sent, `instruct` wins. OpenAI voice names such as `alloy` map to the engine default; they are not different people.

### 5.2 `POST /generate`

`multipart/form-data` fields include `text` (required), `language`, `instruct`, `speed`, `duration`, `seed`, `num_step`, `engine=omnivoice`, `ref_audio` (file), `ref_text`, `postprocess_output`, `stream`, and others listed in `/openapi.json`.

Successful response: WAV, with headers:

```
X-Audio-Id: a0244561
X-Gen-Time: 45.46
X-Audio-Duration: 3.46
X-Seed: 42
X-Audio-Path: a0244561.wav
Content-Type: audio/wav
```

Those values are from the live pause-tag test on this server.

Output audio is **24 kHz mono**.

---

## 6. Parameter reference

| Parameter | Where | Default | Status | What actually happens |
|---|---|---|---|---|
| `input` / `text` | both | required | Native | The words to speak. Put reaction tags here, not in `instruct`. |
| `language` | both | omit / `Auto` | Native | Guides synthesis; does not translate. ISO-style codes such as `en`, `hi`, `es`, `fr`, `ja` work. `Auto` leaves language-agnostic synthesis. |
| `instruct` | both | none | Via instruct (fixed list) | Comma-separated voice-design tags only (gender, age, pitch, `whisper`, English accent, Chinese dialect). Unknown words cause an error on `instruct`. |
| `instructions` | `/v1/audio/speech` | none | Sanitised | OpenAI-style free prose is **stripped** to known tags. Emotion sentences such as “speak sadly” have no effect. |
| `seed` | both | unpinned | Native | Fixes the designed voice and variation. Use `42` to reuse the narrator from earlier clips on this server. |
| `voice` | `/v1/audio/speech` | `default` | Native | `default` / OpenAI aliases → engine default. Otherwise a saved profile id or name. |
| `speed` | both | `1.0` | Native for **faster** only | Values **> 1** shorten the spoken audio (tested). Values **< 1** did **not** reliably slow the words (tested at 0.5, 0.75, 0.85). |
| `duration` | both | unset | Weak / not a WPM control | Aimed at a fixed file length in seconds and overrides `speed`. In testing, `duration=6` mostly **added trailing silence**; the words were not clearly slower. |
| `num_step` | both | `16` | Native | Diffusion steps. `16` is the app default (faster). `32` is the documented quality preset (slower). |
| `guidance_scale` | both | `2.0` | Native | Classifier-free guidance. Leave at 2.0 unless you are tuning quality. |
| `response_format` | `/v1/audio/speech` | `mp3` | Native | `mp3`, `wav`, `opus`, `aac`, `flac`, `pcm` (24 kHz 16-bit LE mono). |
| `[laughter]` `[sigh]` | in the text | — | Via text tags | Native non-verbal tokens. The words “laughter” / “sigh” are not spoken. |
| `[pause]`, `[pause 800ms]`, `[pause 1s]` | in the text | 350 ms if bare | Via text tags | Inserted silence (works on every engine). Upper bound 10 s. |
| `[confirmation-en]` and other interjections | in the text | — | Via text tags | Tokenized by OmniVoice; most `-ah` / `-yi` / `-hnn` variants are tuned for Mandarin-flavoured speech. Not re-auditioned here. |
| `[sad]` `[happy]` `[angry]` `[breath]` `[excited]` | in the text | — | **Not supported** | Unrecognised tags are **not stripped**. `[sad]` was spoken as the word “sad”. |
| `whisper` | in `instruct` | — | Via instruct | The only delivery **style** in the voice-design list. |
| `emo_text`, `emo_alpha`, `emo_vector` | `/generate` | unset | **Not supported** here | OmniVoice returns **HTTP 422**: “does not support emotion controls. Choose IndexTTS2.” |
| `ref_audio` + `ref_text` | `/generate` | unset | Native (not re-tested here) | Zero-shot clone. Best with 3–10 s of clean speech. A transcript of the clip improves conditioning. Combined with `instruct`, the reference wins if they conflict. |
| `profile_id` / `voice` | both | unset | Native (not re-tested here) | Reuse a saved designed or cloned profile. One built-in profile, `demo0001` (“Demo Voice”), is listed on this server. |
| `[slow]` `[fast]` `[emphasis]` `[voice:NAME]` | text | — | Not on these routes | Parsed only in the Audiobook / Stories longform UI, not on `/generate` or `/v1/audio/speech`. |
| `model` | `/v1/audio/speech` | `omnivoice` | Native | Keep `omnivoice`. `tts-1` is an alias for the active engine. |

---

## 7. Words per minute

There is **no `wpm` field**.

### 7.1 Measure a baseline

Use a representative line, the same `instruct` and `seed`, and `speed=1.0`. Then:

```text
baseline_wpm = word_count / (file_duration_seconds / 60)
```

Word count is whitespace-separated words, with bracket tags such as `[laughter]` removed. This is reliable for English. For Hindi and other scripts, time a representative line rather than trusting a word count.

On this server, the 14-word English line

> Please leave the package by the door and I will collect it after lunch.

with `instruct=female, young adult, moderate pitch` and `seed=42` measured:

| | File length | Spoken (silence trimmed) |
|---|---|---|
| Duration | 4.331 s | 3.907 s |
| WPM | **193.9** | **215** |

Short lines look slightly fast because there is little pausing. Measure with your real scripts before you pick a target.

### 7.2 Faster speech — native `speed`

```text
speed = target_wpm / baseline_wpm
```

Clamp to `0.25–4.0`. This worked when `speed` was **greater than 1**:

| Requested `speed` | Expected file length | Actual file length | Spoken length | Result |
|---|---|---|---|---|
| 1.0 | — | 4.331 s | 3.907 s | Baseline (~194 WPM file) |
| 1.5 | 2.89 s | **2.767 s** | 2.480 s | Honoured (~1.57× shorter) |
| 2.0 | 2.17 s | **2.218 s** | 2.131 s | Honoured (~1.95× shorter) |

### 7.3 Slower speech — do not trust `speed < 1` or `duration`

These live requests did **not** slow the articulation:

| Request | File length | Spoken length | What happened |
|---|---|---|---|
| `speed=0.5` (expect ~8.7 s) | 4.282 s | 4.172 s | Almost the same as normal |
| `speed=0.75` (expect ~5.8 s) | 4.023 s | 3.900 s | Same spoken length as normal |
| `speed=0.85` (expect ~5.1 s) | 5.019 s | 3.565 s | File got longer because of padding; the words were not slower |
| `duration=6.0` | 5.580 s | 4.404 s | About 0.95 s of **trailing silence**; speech stayed near the natural rate |

So: **`duration` is not a WPM control on this deployment**, and **`speed` below 1 is not reliable**.

### 7.4 Recommended slower-WPM method (client-side)

Generate at `speed=1.0`, then time-stretch without changing pitch:

```text
atempo = target_wpm / baseline_wpm
```

```bash
# 194 WPM → 140 WPM  =>  atempo=0.722
ffmpeg -y -i normal.mp3 -filter:a "atempo=0.722" slow_140wpm.mp3
```

ffmpeg `atempo` accepts **0.5–2.0** per filter. To go slower than half speed, chain filters, for example `atempo=0.5,atempo=0.8` for 0.4×.

You can also insert pauses in the script with `[pause 800ms]` if you want space between phrases rather than a uniformly slower voice.

The helper functions `speed_for_wpm`, `atempo_for_wpm` and `words_per_minute` in `examples/voicestudio_client.py` (and the same names in `examples/voicestudioClient.mjs`) implement these formulae.

---

## 8. Language

Pass `language` as a VoiceStudio / ISO-style code (`en`, `hi`, `es`, …) or a language name the engine lists. The catalog has **646 languages**. A full table lives in the product docs (`docs/languages.md`). Coverage quality follows training hours: English and Chinese are the strongest; Hindi is supported and was tested on this server.

The picker **does not translate**. If you send English text with `language=hi`, you still get English words (possibly with an odd cadence). Send Hindi text for Hindi speech.

Common codes:

| Language | `language` | ISO 639-3 | Training hours (catalog) |
|---|---|---|---|
| English | `en` | eng | 206,061 |
| Chinese | `zh` | cmn | 111,343 |
| Japanese | `ja` | jpn | 36,914 |
| Spanish | `es` | spa | 27,560 |
| French | `fr` | fra | 23,675 |
| German | `de` | deu | 21,927 |
| Russian | `ru` | rus | 20,339 |
| Portuguese (Brazil) | `pt` or `pt-BR` | por | 16,855 |
| Portuguese (Portugal) | `pt-PT` | por | (same model; European number words) |
| Korean | `ko` | kor | 8,609 |
| Vietnamese | `vi` | vie | 8,482 |
| Indonesian | `id` | ind | 6,328 |
| Italian | `it` | ita | 9,402 |
| Thai | `th` | tha | 10,500 |
| Hindi | `hi` | hin | 117 |
| Bengali | `bn` | ben | 272 |
| Tamil | `ta` | tam | 423 |
| Telugu | `te` | tel | 230 |
| Marathi | `mr` | mar | 157 |
| Gujarati | `gu` | guj | 91 |
| Urdu | `ur` | urd | 211 |
| Punjabi (Western) | see catalog (`lah` / Western Panjabi) | — | — |
| Arabic (Standard) | `ar` / standard arabic | — | listed under regional Arabic varieties |
| Turkish | `tr` | tur | 125 |
| Polish | `pl` | pol | 912 |
| Dutch | `nl` | nld | 2,264 |
| Swedish | `sv` | swe | 2,453 |
| Greek | `el` | ell | 2,413 |
| Hebrew | `he` | heb | 13 |
| Persian | `fa` | fas | 366 |
| Malayalam | `ml` | mal | 167 |
| Kannada | `kn` | kan | 128 |
| Odia | `ory` | ory | 145 |

`GET /engines/tts` returns the live `supported_language_names` list for OmniVoice.

**Tested here:** English (`en`) and Hindi (`hi`) produced the requested language (Hindi transcript matched the script). Earlier work on this same server also narrated Spanish, French and Japanese successfully with the same designed voice.

---

## 9. Voice (design, seed, cloning)

### 9.1 Designed voice — `instruct` + `seed`

`instruct` is a comma-separated list of **whitelist tags**. One tag per category. Case-insensitive. English and Chinese tags can be mixed; the model normalises them.

**Gender:** `male`, `female`  
**Age:** `child`, `teenager`, `young adult`, `middle-aged`, `elderly`  
**Pitch:** `very low pitch`, `low pitch`, `moderate pitch`, `high pitch`, `very high pitch`  
**Style:** `whisper` (only)  
**English accent** (only when the spoken text is English): `american accent`, `british accent`, `australian accent`, `canadian accent`, `indian accent`, `chinese accent`, `korean accent`, `japanese accent`, `portuguese accent`, `russian accent`  
**Chinese dialect** (only when the spoken text is Chinese): `河南话`, `陕西话`, `四川话`, `贵州话`, `云南话`, `桂林话`, `济南话`, `石家庄话`, `甘肃话`, `宁夏话`, `青岛话`, `东北话`

Example used for the clips on this server:

```text
female, young adult, moderate pitch
```

Other valid examples: `male, elderly, low pitch, whisper` and `female, young adult, high pitch, british accent`.

Do **not** put mood words in `instruct`. This request was rejected in 59 ms:

```text
instruct=female, young adult, sad
```

HTTP **500** (OpenAI error envelope) with:

```text
Unsupported instruct items found in female, young adult, sad:
  'sad' -> 'sad' (unsupported)
```

and a list of the valid tags. Always treat “sad / happy / angry” as invalid instruct items.

Pin `seed` (integer) so later lines match. Unpinned seeds produce a different take each time.

### 9.2 Voice cloning

On `POST /generate`, upload a short clean recording as `ref_audio` (WAV, MP3 or M4A). Optionally send `ref_text` — the transcript of **that clip**, in the clip’s own language. Keep the new script in `text` in the language you want spoken.

Sweet spot: **3–10 seconds**. A clip with a transcript is limited to 20 seconds. Without a transcript the engine may search a longer file for a speech window, up to 75 seconds.

On `POST /v1/audio/speech`, set `voice` to a saved profile id (or name) instead of uploading a file.

Cloning is implemented and documented by the engine. It was **not re-tested** in this SOP run. If you add it, record one successful request in your own test suite.

---

## 10. Tone, emotion, laugh

| Goal | Do this | Do not do this |
|---|---|---|
| Whisper | `instruct="female, young adult, moderate pitch, whisper"` | `[whisper]` in the text, or “please whisper” in `instructions` |
| Laugh | `That was hilarious. [laughter] I cannot believe it.` | `instruct="laughing"` or `emo_text="laugh"` |
| Sigh | `I waited all day. [sigh] Nothing happened.` | The word “sigh” alone, or `[breath]` |
| Pause | `Wait here. [pause 800ms] Now you may go.` | Relying on `duration` to insert a mid-sentence rest |
| Sad / happy / angry | **Not available** on this engine. Write the wording you want (and punctuation). That changes the script, not a true emotion control. | `instruct="sad"`, `emo_text="sad"`, `[sad]`, `[happy]`, `[angry]`, “speak sadly” in `instructions` |

Live checks:

- `POST /generate` with `emo_text=sad` → **422** `omnivoice does not support emotion controls. Choose IndexTTS2.`
- `instruct="female, young adult, sad"` → **500** unsupported instruct item (see §9).
- OpenAI `instructions="speak in a sad, angry, crying voice"` without a valid `instruct` → tags dropped; the test take was effectively silent. Always send a valid `instruct` (or a cloned profile).
- Text `I am so [sad] today.` → the model said **“I am so sad today.”** The tag was spoken as a word. Clip: `samples/sad.mp3`.
- `[laughter]` → the word “laughter” was not spoken; a non-speech burst sits between the two sentences. Clip: `samples/laugh.mp3`.
- `[sigh]` → the word “sigh” was not spoken; a breathy stretch sits between the two clauses. Clip: `samples/sigh.mp3`.
- `instruct` + `whisper` → same words and length as the normal take, about **7 dB quieter** (speech RMS 0.068 vs 0.154). Clip: `samples/whisper.mp3`.
- `[pause 800ms]` → about **1060 ms** of mid-clip silence (the engine also adds a little of its own padding). Clip: `samples/pause.mp3`.

Honest expectation from the engine docs, confirmed in spirit here: `[laughter]` and `[sigh]` are the broadly useful tags; how strong they sound varies by voice. There is no intensity slider.

---

## 11. Recipes

Replace the base URL with `http://127.0.0.1:3900` and drop the `Authorization` header if you are calling from the VPS itself.

Reusable modules (preferred): `examples/voicestudio_client.py` and `examples/voicestudioClient.mjs`. Usage: `examples/example_usage.py` and `examples/example_usage.mjs`.

### 11.1 curl — normal English speech

```bash
curl -sS --max-time 900 \
  -X POST http://130.250.191.136:8787/v1/audio/speech \
  -H "Authorization: Bearer $VOICESTUDIO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "omnivoice",
    "input": "Please leave the package by the door and I will collect it after lunch.",
    "voice": "default",
    "language": "en",
    "instruct": "female, young adult, moderate pitch",
    "seed": 42,
    "speed": 1.0,
    "num_step": 16,
    "response_format": "mp3"
  }' \
  --output normal.mp3
```

### 11.2 curl — faster speech

Same body, with `"speed": 1.5` (or `2.0`). Save as `fast.mp3`.

### 11.3 curl — slower speech (after generation)

```bash
ffmpeg -y -i normal.mp3 -filter:a "atempo=0.722" slow_140wpm.mp3
```

### 11.4 curl — Hindi

```bash
curl -sS --max-time 900 \
  -X POST http://130.250.191.136:8787/v1/audio/speech \
  -H "Authorization: Bearer $VOICESTUDIO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "omnivoice",
    "input": "कृपया पैकेज दरवाज़े के पास छोड़ दें, मैं दोपहर बाद उसे ले लूँगा।",
    "voice": "default",
    "language": "hi",
    "instruct": "female, young adult, moderate pitch",
    "seed": 42,
    "response_format": "mp3"
  }' \
  --output hindi.mp3
```

### 11.5 curl — whisper, laugh, sigh, pause

```bash
# Whisper: add the style tag to instruct
# "instruct": "female, young adult, moderate pitch, whisper"

# Laugh / sigh / pause belong in the text:
# "input": "That was hilarious. [laughter] I cannot believe what just happened."
# "input": "I waited all day. [sigh] Nothing happened after all."
# "input": "Wait here. [pause 800ms] Now you may go."
```

### 11.6 curl — native `/generate` (WAV + timing headers)

```bash
curl -sS --max-time 900 \
  -X POST http://130.250.191.136:8787/generate \
  -H "Authorization: Bearer $VOICESTUDIO_API_KEY" \
  -F "text=Wait here. [pause 800ms] Now you may go." \
  -F "language=en" \
  -F "instruct=female, young adult, moderate pitch" \
  -F "seed=42" \
  -F "speed=1.0" \
  -F "num_step=16" \
  -F "engine=omnivoice" \
  --output pause.wav -D pause.headers
```

### 11.7 Python (module + call)

```python
import os
from voicestudio_client import VoiceStudioClient, atempo_for_wpm, speed_for_wpm

client = VoiceStudioClient(
    base_url="http://130.250.191.136:8787",
    api_key=os.environ["VOICESTUDIO_API_KEY"],
)

text = "Please leave the package by the door and I will collect it after lunch."
client.speak(text, language="en", dest="normal.mp3")
client.speak(text, speed=speed_for_wpm(300, 194), dest="fast.mp3")
client.speak(
    "कृपया पैकेज दरवाज़े के पास छोड़ दें, मैं दोपहर बाद उसे ले लूँगा।",
    language="hi",
    dest="hindi.mp3",
)
client.speak(
    "That was hilarious. [laughter] I cannot believe what just happened.",
    dest="laugh.mp3",
)

# Slower WPM: generate normally, then stretch
factor = atempo_for_wpm(140, 194)  # 0.722
# ffmpeg -y -i normal.mp3 -filter:a "atempo=0.722" slow.mp3
```

### 11.8 JavaScript (Node 18+, module + call)

```javascript
import { VoiceStudioClient, speedForWpm, atempoForWpm } from "./voicestudioClient.mjs";

const client = new VoiceStudioClient({
  baseUrl: "http://130.250.191.136:8787",
  apiKey: process.env.VOICESTUDIO_API_KEY,
});

await client.speak("Please leave the package by the door and I will collect it after lunch.", {
  dest: "normal.mp3",
});
await client.speak("Please leave the package by the door and I will collect it after lunch.", {
  speed: speedForWpm(300, 194),
  dest: "fast.mp3",
});
console.log("slow-speech atempo factor", atempoForWpm(140, 194).toFixed(3));
```

---

## 12. Limits and timing on this server

| Topic | Value |
|---|---|
| Engine / device | OmniVoice 0.5.7, **CPU**, float32, no GPU |
| `/v1/audio/speech` text limit | 4096 characters |
| Long text on `/generate` | Split at about 800 characters by default (`max_chunk_chars`) |
| Output | 24 kHz mono |
| Warm real-time factor | Typically **9–14×** (a 4 s clip takes ~40–60 s). Measured range on these tests: 8.6× to 16×; one later 2×-speed clip was slower (about 35×). Plan for **about 11×** when the model is warm |
| First request after idle | Can be slower (model already resident after recent use; a true cold start is worse) |
| HTTP timeout you should set | **900 s** is a safe client default; the server CPU auto-ceiling is 7200 s |
| Concurrency | One generate at a time is the safe pattern. A busy worker returns **503** with `Retry-After` and `X-OmniVoice-Retryable: true` |
| `num_step` | 16 (faster, used in these tests) or 32 (cleaner, roughly twice the generate time) |
| RAM | Recent sessions on this host peaked around 2.6 GB system / ~3.7 GB process RSS — not the limiting factor. Time is |

---

## 13. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `401` `API key required` | Missing or wrong `Authorization` header, or calling port 8787 without a key | Send `Authorization: Bearer $VOICESTUDIO_API_KEY`. Loopback `:3900` does not need it |
| `422` emotion controls / IndexTTS2 | You sent `emo_text` or `emo_vector` | Drop those fields. OmniVoice cannot do graded emotion |
| `500` / `Unsupported instruct items` | Mood or prose in `instruct` (`sad`, “speak warmly”, …) | Use only the whitelist in §9. Put laugh/sigh/pause in the **text** |
| The voice says the word “sad” (or “happy”) | You put `[sad]` in the script | Remove the tag. It is not an emotion control |
| Slow `speed` did not slow the voice | Native limitation, confirmed on this host | Time-stretch with `atempo` after generation |
| `duration` made a longer file that still sounds rushed | Trailing silence was added; articulation barely changed | Do not use `duration` for WPM |
| Hindi (or another language) still sounds English | The `text` is still English, or `language` is wrong | Send text in the target language; set `language` to match |
| Almost silent take | `instructions` prose was stripped and no valid `instruct` or clone was left | Always send a valid `instruct` or a cloned / saved voice |
| Request times out at 60–120 s | Client timeout is too short for CPU generation | Raise it to 15 minutes |
| `503` with `Retry-After` | Another generate is running | Wait and retry once; do not stampede |
| Connection refused on `:3900` from your laptop | That port is localhost-only | Use `http://130.250.191.136:8787` with the key |
| First call is very slow or errors | Cold model load | Retry once; `/health` and `/engines/tts` should already be `ok` / `available` |

---

## 14. Live test log (10 November 2026, Asia/Calcutta)

All generation used the designed voice `female, young adult, moderate pitch` and `seed=42` unless noted. Calls went to the loopback API on the VPS (`127.0.0.1:3900`), which is the same engine the public proxy exposes. Public key authentication was tested separately against port 8787.

| Test | Result | Clip |
|---|---|---|
| `emo_text=sad` | **Fail as designed** — HTTP 422 in 0.02 s | — |
| `instruct=…, sad` | **Fail as designed** — HTTP 500, unsupported item, 0.06 s | — |
| OpenAI `instructions` emotion prose only | Tags dropped; take was effectively silent | — |
| Normal English, `speed=1.0` | **Pass** — 4.331 s audio, 46.0 s generate, 10.6× RTF, 193.9 WPM | `samples/normal.mp3` |
| `speed=0.75` / `0.5` / `0.85` | **Did not slow speech** (see §7) | `samples/slow.mp3`, `slow_050.mp3`, `slow_085.mp3` |
| `speed=1.5` | **Pass** — 2.767 s file, 1.57× shorter | `samples/fast.mp3` |
| `speed=2.0` | **Pass** — 2.218 s file, 1.95× shorter | `samples/fast-2x.mp3` |
| `duration=6.0` | File 5.58 s, but ~0.95 s trailing silence; words not clearly slower | `samples/duration-6s.mp3` |
| Hindi, `language=hi` | **Pass** — 3.783 s; recogniser returned the Hindi script | `samples/hindi.mp3` |
| `instruct` + `whisper` | **Pass** — same length, ~7 dB quieter | `samples/whisper.mp3` |
| `[laughter]` | **Pass** — non-verbal burst between sentences; “laughter” not spoken | `samples/laugh.mp3` |
| `[sigh]` | **Pass** — breathy stretch between clauses; “sigh” not spoken | `samples/sigh.mp3` |
| `[sad]` in the text | **Fail as a control** — spoken as “I am so sad today.” | `samples/sad.mp3` |
| `[pause 800ms]` | **Pass** — ~1060 ms mid-clip silence; headers returned | `samples/pause.mp3` |
| Public `GET /engines` without key | **Pass as designed** — 401 | — |
| Public `GET /engines/tts` with key | **Pass** — 200, active engine `omnivoice` | — |

Raw measurements: `tests/audio/results.json` and `tests/audio/test.log`.

---

## 15. Sample clips and example code

All paths are relative to this folder (`voicestudio-sop/` in the delivery package). The Markdown is also in the product repo at `docs/VOICESTUDIO_API_SOP.md`.

| File | What it demonstrates |
|---|---|
| `samples/normal.mp3` | Baseline English, designed voice, seed 42 |
| `samples/fast.mp3` | Native `speed=1.5` |
| `samples/fast-2x.mp3` | Native `speed=2.0` |
| `samples/slow.mp3`, `slow_050.mp3`, `slow_085.mp3` | Evidence that `speed < 1` did not slow the words |
| `samples/duration-6s.mp3` | `duration=6` (mostly trailing silence) |
| `samples/hindi.mp3` | Hindi text + `language=hi` |
| `samples/whisper.mp3` | `whisper` in `instruct` |
| `samples/laugh.mp3` | `[laughter]` |
| `samples/sigh.mp3` | `[sigh]` |
| `samples/sad.mp3` | `[sad]` read as the word “sad” (anti-example) |
| `samples/pause.mp3` | `[pause 800ms]` |
| `examples/voicestudio_client.py` | Reusable Python client + WPM helpers |
| `examples/voicestudioClient.mjs` | Reusable Node client + WPM helpers |
| `examples/example_usage.py` | Copy-paste recipes, including `atempo` for slow WPM |
| `examples/example_usage.mjs` | Same recipes in JavaScript |

---

*VoiceStudio 0.5.7, OmniVoice, CPU VPS 130.250.191.136. SOP verified on 10 November 2026, Asia/Calcutta.*
