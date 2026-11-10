(function () {
  "use strict";

  const api = window.VoiceStudioAPI;
  const form = document.getElementById("speak-form");
  const textEl = document.getElementById("text");
  const charCount = document.getElementById("char-count");
  const textFile = document.getElementById("text-file");
  const languageFilter = document.getElementById("language-filter");
  const languageEl = document.getElementById("language");
  const wpmEl = document.getElementById("wpm");
  const wpmNumber = document.getElementById("wpm-number");
  const durationHint = document.getElementById("duration-hint");
  const voiceList = document.getElementById("voice-list");
  const voicesUi = window.VoiceStudioVoices;
  const referenceEl = document.getElementById("reference");
  const referenceHint = document.getElementById("reference-hint");
  const generateBtn = document.getElementById("generate");
  const statusEl = document.getElementById("status");
  const statusTitle = document.getElementById("status-title");
  const statusDetail = document.getElementById("status-detail");
  const resultEl = document.getElementById("result");
  const player = document.getElementById("player");
  const resultMeta = document.getElementById("result-meta");
  const download = document.getElementById("download");
  const errorEl = document.getElementById("error");

  let meta = {
    max_chars: 500,
    min_wpm: 80,
    max_wpm: 220,
    default_wpm: 150,
    min_duration_s: 1,
    max_duration_s: 45,
    cpu_realtime_factor: 11,
    baseline_wpm: 194,
    poll_interval_ms: 2500,
    voices: [],
    default_voice: "narrator"
  };
  let allLanguages = [];
  let objectUrl = null;
  let timerId = null;
  let startedAt = 0;

  function showError(message) {
    errorEl.hidden = !message;
    errorEl.textContent = message || "";
  }

  function formatSeconds(value) {
    if (!value && value !== 0) return "—";
    if (value < 60) return value.toFixed(1) + " s";
    const minutes = Math.floor(value / 60);
    const seconds = Math.round(value % 60);
    return minutes + " min " + seconds + " s";
  }

  function formatElapsed(ms) {
    const total = Math.max(0, Math.floor(ms / 1000));
    const m = Math.floor(total / 60);
    const s = total % 60;
    return m + ":" + String(s).padStart(2, "0");
  }

  function updateCounts() {
    const max = meta.max_chars || 500;
    const length = Array.from(textEl.value).length;
    charCount.textContent = length + " / " + max;
    charCount.style.color = length >= max ? "#9b2c2c" : "";
    const wpm = Number(wpmEl.value) || meta.default_wpm;
    const est = api.planFromWpm(textEl.value, wpm, meta.baseline_wpm || 194, meta.min_duration_s, meta.max_duration_s);
    const wait = est.generateDuration * (meta.cpu_realtime_factor || 11);
    if (!est.words) {
      durationHint.textContent = "At " + wpm + " words per minute this will be about 0 seconds of audio.";
      return;
    }
    durationHint.textContent =
      est.words + " word" + (est.words === 1 ? "" : "s") +
      " at " + wpm + " WPM ≈ " + formatSeconds(est.duration) + " of audio" +
      (est.capped ? " (capped at the server limit)" : "") +
      ". Expected generation time on this CPU is about " + formatSeconds(wait) + ".";
  }

  function fillVoices(savedVoices) {
    const presets = meta.voices && meta.voices.length ? meta.voices : [
      { id: "narrator", label: "Priya", blurb: "young female" }
    ];
    const list = voicesUi.mergeLists(savedVoices || [], presets, meta.default_voice || "narrator");
    voicesUi.render(voiceList, list, meta.default_voice || "narrator");
  }

  function renderLanguages(filter) {
    const needle = (filter || "").trim().toLowerCase();
    const current = languageEl.value || "en";
    const featured = [];
    const rest = [];
    for (const lang of allLanguages) {
      const hay = (lang.name + " " + lang.id).toLowerCase();
      if (needle && hay.indexOf(needle) === -1) continue;
      (lang.featured ? featured : rest).push(lang);
    }
    languageEl.innerHTML = "";
    function addGroup(label, items) {
      if (!items.length) return;
      const group = document.createElement("optgroup");
      group.label = label;
      for (const lang of items) {
        const opt = document.createElement("option");
        opt.value = lang.id;
        opt.textContent = lang.name + " (" + lang.id + ")";
        group.appendChild(opt);
      }
      languageEl.appendChild(group);
    }
    addGroup("Common languages", featured);
    addGroup("All OmniVoice languages", rest);
    if (Array.from(languageEl.options).some((opt) => opt.value === current)) {
      languageEl.value = current;
    } else if (languageEl.options.length) {
      languageEl.selectedIndex = 0;
    }
  }

  function syncWpm(from) {
    if (from === "slider") wpmNumber.value = wpmEl.value;
    else wpmEl.value = wpmNumber.value;
    updateCounts();
  }

  let expectedWaitS = 0;
  let lastJobStatus = null;

  function startTimer(expectedS) {
    startedAt = Date.now();
    expectedWaitS = expectedS;
    lastJobStatus = null;
    statusEl.hidden = false;
    resultEl.hidden = true;
    statusTitle.textContent = "Generating…";
    const tick = () => {
      const elapsed = Date.now() - startedAt;
      let detail = "Elapsed " + formatElapsed(elapsed) +
        ". Typical wait is about " + formatSeconds(expectedWaitS) +
        " on this CPU server (about 11× the natural audio length).";
      if (lastJobStatus) {
        if (lastJobStatus.status === "queued") {
          statusTitle.textContent = "Queued…";
          detail = "Position " + (lastJobStatus.position || 1) + " in the queue. " + detail;
        } else if (lastJobStatus.status === "running") {
          statusTitle.textContent = "Generating…";
        }
      }
      statusDetail.textContent = detail;
    };
    tick();
    clearInterval(timerId);
    timerId = setInterval(tick, 500);
  }

  function stopTimer() {
    clearInterval(timerId);
    timerId = null;
    statusEl.hidden = true;
  }

  textEl.addEventListener("input", updateCounts);
  wpmEl.addEventListener("input", () => syncWpm("slider"));
  wpmNumber.addEventListener("input", () => syncWpm("number"));
  languageFilter.addEventListener("input", () => renderLanguages(languageFilter.value));

  textFile.addEventListener("change", async () => {
    const file = textFile.files && textFile.files[0];
    if (!file) return;
    const raw = await file.text();
    textEl.value = raw.slice(0, meta.max_chars || 500);
    updateCounts();
    textFile.value = "";
  });

  referenceEl.addEventListener("change", () => {
    const file = referenceEl.files && referenceEl.files[0];
    referenceHint.textContent = file
      ? ("Using " + file.name + " as the reference voice.")
      : "Upload a short clip to clone that voice. Leave empty to use the voice above.";
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError("");
    const text = textEl.value.trim();
    if (!text) {
      showError("Please enter some text to narrate.");
      return;
    }
    const wpm = Number(wpmEl.value);
    const est = api.planFromWpm(text, wpm, meta.baseline_wpm || 194, meta.min_duration_s, meta.max_duration_s);
    generateBtn.disabled = true;
    startTimer(est.generateDuration * (meta.cpu_realtime_factor || 11));
    try {
      const result = await api.generate({
        text,
        language: languageEl.value,
        wpm,
        voice: voicesUi.selected(voiceList),
        reference: referenceEl.files && referenceEl.files[0]
      }, {
        pollIntervalMs: meta.poll_interval_ms || 2500,
        onStatus: function (job) { lastJobStatus = job; }
      });
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = URL.createObjectURL(result.blob);
      player.src = objectUrl;
      player.load();
      const ext = (result.contentType || "").indexOf("mpeg") !== -1 ? "mp3" : "wav";
      download.href = objectUrl;
      download.download = "voicestudio-" + result.language + "-" + Math.round(result.targetDuration) + "s." + ext;
      const actual = player.duration;
      resultMeta.textContent =
        result.wordCount + " words at " + result.wpm + " WPM" +
        " · target " + formatSeconds(result.targetDuration) +
        (result.capped ? " (capped)" : "") +
        " · " + result.language +
        " · " + result.voice +
        (result.method ? " · " + result.method : "") +
        " · generated in " + formatElapsed(Date.now() - startedAt) + ".";
      resultEl.hidden = false;
      try { await player.play(); } catch (err) { /* autoplay may be blocked */ }
      player.addEventListener("loadedmetadata", function once() {
        if (isFinite(player.duration)) {
          resultMeta.textContent += " Audio length: " + formatSeconds(player.duration) + ".";
        }
        player.removeEventListener("loadedmetadata", once);
      });
    } catch (err) {
      showError(err && err.message ? err.message : "Generation failed.");
    } finally {
      stopTimer();
      generateBtn.disabled = false;
    }
  });

  async function boot() {
    try {
      meta = Object.assign(meta, await api.getJson("/api/meta"));
      textEl.maxLength = meta.max_chars;
      wpmEl.min = wpmNumber.min = meta.min_wpm;
      wpmEl.max = wpmNumber.max = meta.max_wpm;
      wpmEl.value = wpmNumber.value = meta.default_wpm;
      let savedVoices = [];
      try {
        const saved = await api.getJson("/api/voices");
        savedVoices = saved.voices || [];
      } catch (err) {
        savedVoices = [];
      }
      fillVoices(savedVoices);
    } catch (err) {
      fillVoices([]);
      showError("Could not load server settings. You can still try to generate.");
    }
    try {
      const data = await api.getJson("/api/languages");
      allLanguages = data.languages || [];
    } catch (err) {
      allLanguages = [
        { id: "en", name: "English", featured: true },
        { id: "hi", name: "Hindi", featured: true }
      ];
    }
    renderLanguages("");
    languageEl.value = "en";
    updateCounts();
  }

  boot();
})();
