# VoiceStudio User Manual

A plain-language guide to everyday work in VoiceStudio: cloning a voice, designing one, transcribing, dubbing, and telling stories or making an audiobook.

If you run the server, also see the [Install Guide](INSTALL_GUIDE.md) and the [Admin Manual](ADMIN_MANUAL.md).

---

## 1. First visit

1. Open the address you were given, for example `http://voices.example.com` or `http://<server>:8787`.
2. If you see a **Remote backend** card, paste the **API key** your administrator sent you and click **Connect**.
3. The first time, a short setup wizard runs: **System check**, **Model packs**, **Privacy**, then **Enter studio**.
4. You land on **Home**.

There is no username or password. Anyone with the API key can use every feature, including administration. Keep the key private.

Speech needs a model. The default, **OmniVoice**, is about 2.4 GB. The app asks before it downloads. If a feature says a model is missing, go to **Settings → Models** (or ask your administrator) and click **Download**.

---

## 2. Finding your way around

The left-hand **Workspaces** menu is grouped like this:

| Group | Pages |
|---|---|
| **Voice** | **Clone**, **Design**, **Saved**, **Gallery** |
| **Stories** | **Stories**, **Audiobook** |
| **Dubbing** | **Dubbing**, **Batch Dubbing** |
| (standalone) | **Transcribe**, **Workflows**, **Projects**, **Tools**, **Integrations** |

**Home** is the starting page. It lists the same features, your recent projects, saved voices, and recent exports.

Useful everywhere:

- The command palette (search icon, or the button in the header) jumps to any page.
- **Settings** (the gear) is for appearance, models, credentials, and other app options. The **admin** panel at `#/admin` is for the server itself and is covered in the Admin Manual.
- A job you start (a dub, a transcription, a book render) usually keeps running if you leave the page. A toast or the notifications area tells you when it finishes.

---

## 3. Voice cloning

Turn a short recording of a real voice into a reusable voice you can type for.

1. Open **Clone** (Voice → Clone, or the card on Home).
2. Add a **Reference recording**. Use **5–15 seconds of clean speech**. You can:
   - click **Upload audio** (or drop a WAV, MP3, or M4A file onto the page), or
   - click **Record** and speak into the microphone.
3. Optionally fill **Transcript**, **Style**, and **Language**.
4. Type (or **Paste**) the words you want the voice to say into **Script**.
5. Click **Synthesize audio**. The first run may wait while the voice model downloads.
6. Listen in the player. Earlier results sit under **Recent takes**.
7. To keep the voice, click **Save as voice profile**, give it a **name**, and click **Save**. You'll find it later under **Saved**.

**Change voice** swaps the current reference. **Clear** removes it. You can only clone a voice you have the right to use.

---

## 4. Voice design

Create a voice from a description, without a recording.

1. Open **Design**.
2. Under **Describe your voice**, type something like *"a warm elderly British storyteller, slightly raspy"*, or pick a **Starting point**. Either one fills in the details below.
3. Adjust the details if you want, or click **New seed** for a slightly different take of the same idea.
4. Type the **Script**.
5. Click **Synthesize audio**, listen, and, when you like it, **Save as voice profile**.

**Use voice** in the **Gallery** (next section) can also drop a ready-made design into this page.

---

## 5. Saved voices and the Gallery

**Saved** (`#/personas`) is your own library of cloned and designed voices.

**Gallery** has three tabs in the header:

- **Archetypes**: a built-in catalogue. Filter by category, age, gender, pitch, accent, language, or whisper. Star voices to keep them as **Favorites**. Click **Preview** to hear one, then **Use voice** to turn it into a design profile and open **Design**. Your current script is kept.
- **Community**: voices shared by other people, filterable by pack and language. **Open in Design** hands a preset's attributes to Design.
- **My Imports**: paste a URL you have the rights to, or **Upload file**, trim the part you need, and save it as a voice. You can also **Import a .ovsvoice persona bundle**.

---

## 6. Stories

Write a scene or a short script and hear it with one or more voices.

1. Open **Stories**.
2. In the setup card, pick a default voice, a language, and an output format.
3. Type or import the script. Stories accepts TXT, Markdown, and SRT on this page. EPUB and PDF go through an importer. You can also **Paste & Split** into **Sentences**, **Paragraphs** (the default), or **Chapters**.
4. Assign voices to characters (the **Cast** section). **Auto-cast** can pick voices from tagged dialogue or a screenplay, without calling an online language model.
5. Insert a pause with `[pause 0.5s]`. A line can use `[voice:NAME]` to pick a saved voice.
6. Click **Generate**. Progress shows the percentage, elapsed time, and time left. **Stop** cancels the render. Leaving the page does not stop it.
7. When it's done, play it, then export MP3 or M4B through the save dialog. You can also save a cue sheet (a `.txt` file of chapter times and titles).

**Clear script** (with a confirmation) removes the lines but keeps the cast. Named work is saved from the **Projects** tab on this page, or from the **Projects** workspace.

---

## 7. Audiobook

Same idea as Stories, aimed at a full book.

1. Open **Audiobook**.
2. Fill in the book details if you want: author, narrator, year, genre, description, and a JPEG or PNG cover.
3. Paste or import the manuscript. Chapter titles on their own lines are recognized. `# Heading` lines stay as chapters.
4. Set the default voice and language. Names the script mentions but you haven't cast yet are read in the main voice.
5. Optional: **Pronunciation** rows (don't list the same word twice), **Loudness** (*off*, *ACX*, or *podcast*), and production overrides.
6. **Preview plan** shows the chapters. You can audition a chapter before the full render.
7. Click **Generate**. Export **MP3** or **M4B** (M4B can carry chapter markers). A cue sheet is also available.

If a render was interrupted, a card offers **Resume** or **Dismiss**. Resume is disabled while another render is running, or if text-to-speech isn't ready.

---

## 8. Dubbing

Translate a video or audio file and speak it in another language, in voices that follow the original speakers.

1. Open **Dubbing**.
2. Drop a file onto **Drop an audio or video file here**, or **paste a video URL**. Preparation finishes before transcription starts.
3. Under the preview, set **Spoken language** (*Auto* is the default) and the **speaker count**. You can **Import .srt** instead of transcribing.
4. Pick one or more **target languages**. Translation uses the provider chosen in **Settings → Models → Translation**.
5. Click **Translate**, review the text in the transcript (source on the left, translation on the right), then click **Generate** (or **Generate Dub**).
6. Preview the result and **Export** as **MP4**, **WAV**, or **SRT**.

Useful details:

- **File actions** on a loaded file: **Change file**, **Use link**, and **Remove video** (or **Remove audio**). Remove asks for confirmation if you have unsaved edits.
- Each line has a speaker and a voice. From the speaker header you can move a line to another speaker or a **New speaker**.
- When several languages are selected, tabs above the transcript switch between them. **Translate every segment** covers all of them.
- A **Projects** tab on this page lists saved dubs. The **Projects** workspace is where you rename or delete them.
- Translation needs an OpenAI key, an Ollama (or other compatible) server, or another translation provider configured in Settings or by your administrator.

---

## 9. Batch Dubbing

For several files at once, without the per-line editor.

1. Open **Batch Dubbing**.
2. Add videos (click or drag and drop).
3. Choose one or more target languages, optionally a saved voice, and whether to keep the background audio.
4. Click **Add to Queue**. Files that are accepted leave the list; ones that failed stay so you can retry.
5. Watch **Active**, **Completed**, and **Failed**. You can cancel a running job. Deleting a finished record asks for confirmation. Completed languages use the save dialog.

The queue lives in the server's memory: a restart of the app loses unfinished jobs.

---

## 10. Transcribe and dictation

Turn speech into text.

1. Open **Transcribe**.
2. Choose **Transcription quality**: **Fast** (the low-latency dictation model) or **Accurate** (the speech-to-text model, with timestamps).
3. Click **Start dictation** and speak, then stop, **or** upload an audio file.
4. The transcript appears in the workspace. A **History** pane keeps earlier results (newest first). You can search, copy, export, or delete an entry, or send the text to the cloning script.

**Identify speakers** (off by default, Accurate mode only) labels who spoke each segment. If the speaker model isn't installed or fails, the transcript is still saved, without labels.

File transcription keeps running if you leave the page; only **Cancel** stops it. A toast brings you back when it finishes. Live dictation from a system-wide shortcut is a desktop feature (see Settings). On the web, use **Start dictation** on this page.

---

## 11. Workflows and Calls

**Workflows** is a canvas of steps you run over many inputs. **Calls** is a related view for phone-call drafts; a button takes you back to the canvas.

Typical templates:

- **Batch narration**: paste scripts separated by a line with `---`, or import TXT, Markdown, DOC/DOCX, PDF, or EPUB (up to 50 scripts, 20,000 characters each). Choose a saved voice, language, and speed, then **Run workflow**.
- **Audio to transcript**: import audio → Transcribe → export TXT.
- **Change the voice**: import audio → Convert with a saved voice → export WAV.
- **Translate and narrate**: import audio → Transcribe → Translate → Speak → export WAV.

Audio inputs: up to 50 files, each no larger than 64 MiB. **Run workflow** stays disabled until every step that **Needs setup** is filled in.

---

## 12. Projects

**Projects** lists your saved **Dubbing**, **Stories**, and **Audiobook** work, newest first. Open a row to continue it in the matching workspace. You can rename or delete from here. Home also shows a short "recent" list.

---

## 13. Tools

**Tools** opens utility panes, plus **A/B Voice Comparison** and **Convert**:

| Tool | What it does |
|---|---|
| **Directorial AI** | You describe how a line should sound. The tool shows style tags, a speech instruction, a translation hint, and pace. Click **Parse**. |
| **Speech-rate fit** | Paste a translated line, enter a **Slot (seconds)** greater than zero, pick a **Target language**, and click **Fit**. |
| **Probe file** | Type an absolute path to a media file and click **Probe**. It reports codecs, streams, and duration without changing the file. |
| **Convert** | Pick a saved voice, upload or record a clip, and resynthesize it in that voice. **Match duration** changes the overall length only. **Keep my delivery** keeps the original timing and intonation (needs CosyVoice 3 installed, and a voice with a reference recording). Clips longer than about 28 seconds are split at pauses; sources over 10 minutes are refused. |
| **A/B Voice Comparison** | Compare two voices side by side. |

Each tool runs only when you click its button. Switching tools cancels the previous request.

---

## 14. Integrations

**Integrations** is a catalogue of ways to hook VoiceStudio into other software (for example MCP, n8n, or telephony). Open an item for its own setup page. These are optional; everyday cloning, dubbing, and transcription don't need them.

---

## 15. Settings (for everyone)

Open **Settings** from the gear. The list has a search box.

| Section | Typical uses |
|---|---|
| **General** | Interface **Language**, **Review mode** |
| **Appearance** | **Theme**, **Font**, **UI scale**, **Glass mode**, sidebar behaviour |
| **Models** | Download engines, grouped as **TTS**, **ASR**, **Dictation**, **Diarisation**, **Translation**, and **LLM** |
| **Credentials** | Hugging Face token, translation providers, and similar secrets |
| **Network** | Proxy and network options |
| **Sharing & Remote Access** | Sharing the app, or pointing at a remote backend |
| **Performance** | Compute device |
| **Usage** | Usage information |
| **Privacy** | Analytics and related choices |
| **Permissions** | Microphone and other device permissions |
| **Storage** | Where files are kept, and cleanup |
| **Pronunciation dictionary** | Preferred pronunciations (used by Audiobook) |
| **Audio tools** | FFmpeg / ffprobe helpers the app uses |
| **Logs** | Application logs |
| **Updates** | Desktop / app updates (the *server* update button is in the admin panel) |
| **Support** | Support and sponsorship |
| **About** / diagnostics | Version and diagnostics |
| **VoiceStudio API** | Local API documentation |
| **VoiceStudio account** | Optional account features, only if they have been turned on |

If you only use the shared server, ask your administrator before changing **Models**, **Credentials**, or **Performance**. Those settings affect everyone on that server.

---

## 16. FAQ

**The page asks for an API key.**  
Ask the person who installed the server. After they rotate the key, the old one stops working.

**A feature says a model is missing.**  
Open **Settings → Models**, find the model, and click **Download**. For the default voice that's OmniVoice (about 2.4 GB). Speaker labels and some dubbing steps need a diarization model and, often, a Hugging Face token. Translation needs a provider in **Settings → Credentials** or **Models → Translation**.

**Speech is very slow.**  
The server is probably running on CPU. That's expected and much slower than a GPU. Use shorter text, or ask the administrator about a GPU machine.

**The first "Synthesize audio" sits there for a long time.**  
The voice model is downloading or loading into memory. Later runs are faster.

**Can I use this on my phone?**  
The manuals in this folder describe the web app in a browser and the desktop app. A separate mobile app is documented in `docs/mobile.md`.

**Does anything leave my server?**  
Voice generation with the default OmniVoice model runs on the machine. Optional pieces (Hugging Face downloads, a cloud translation API, Community gallery items, a video URL you paste) do use the network. Check **Settings → Privacy**.

**I closed the tab during a dub / transcription / book render.**  
Those jobs usually keep running on the server. Reopen the same page, or check **Projects** and notifications. A restart of the server can drop an in-memory **Batch Dubbing** queue.

**How do I export?**  
Clone and Design takes, dubs, stories, and audiobooks each have an export or download control and a save dialog. Finished work also appears on **Home** and in **Projects**.

**May I clone any voice I find?**  
Only voices you have permission to use. Model weights and generated or cloned audio have their own licences; see `LICENSE-NOTICE.md`.

**I clicked Stop in the admin panel and the site is gone.**  
Only an administrator on the server can start it again: `sudo systemctl start voicestudio-api voicestudio-web`.

**Where is the admin panel?**  
`#/admin`. It is documented in the [Admin Manual](ADMIN_MANUAL.md).
