
/* Admin Voice Training page. Uses the existing admin cookie/session. */
(function () {
  const form = document.getElementById("train-form");
  const nameEl = document.getElementById("name");
  const languageEl = document.getElementById("language");
  const clipsEl = document.getElementById("clips");
  const clipList = document.getElementById("clip-list");
  const consentEl = document.getElementById("consent");
  const trainBtn = document.getElementById("train");
  const statusEl = document.getElementById("status");
  const statusTitle = document.getElementById("status-title");
  const statusDetail = document.getElementById("status-detail");
  const statusBar = document.getElementById("status-bar");
  const errorEl = document.getElementById("error");
  const resultEl = document.getElementById("result");
  const resultDetail = document.getElementById("result-detail");
  const voiceList = document.getElementById("voice-list");

  function showError(message) {
    errorEl.hidden = !message;
    errorEl.textContent = message || "";
  }

  function syncTrainEnabled() {
    const hasName = !!(nameEl.value || "").trim();
    const hasLang = !!(languageEl.value || "").trim();
    const hasClips = clipsEl.files && clipsEl.files.length > 0;
    trainBtn.disabled = !(hasName && hasLang && hasClips && consentEl.checked);
  }

  function renderClipEditors() {
    clipList.innerHTML = "";
    const files = Array.from(clipsEl.files || []);
    files.forEach(function (file, index) {
      const wrap = document.createElement("div");
      wrap.className = "clip";
      const label = document.createElement("label");
      label.setAttribute("for", "transcript-" + index);
      const title = document.createElement("strong");
      title.textContent = file.name + " (" + Math.max(1, Math.round(file.size / 1024)) + " KB)";
      label.appendChild(title);
      const hint = document.createElement("span");
      hint.className = "hint";
      hint.textContent = " Optional transcript. Leave blank to auto-transcribe when a recognizer is available.";
      label.appendChild(hint);
      const area = document.createElement("textarea");
      area.id = "transcript-" + index;
      area.name = "transcript_" + index;
      area.placeholder = "Transcript for this clip (optional)";
      wrap.appendChild(label);
      wrap.appendChild(area);
      clipList.appendChild(wrap);
    });
    syncTrainEnabled();
  }

  async function api(path, options) {
    const response = await fetch(path, Object.assign({ credentials: "include" }, options || {}));
    const text = await response.text();
    let data = {};
    if (text) {
      try { data = JSON.parse(text); } catch (err) { data = { detail: text }; }
    }
    if (response.status === 401 || response.status === 403) {
      throw new Error("Sign in to the admin panel first, then reopen Voice Training.");
    }
    if (!response.ok) {
      const detail = data.detail || data.error || ("Request failed (" + response.status + ")");
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  async function refreshVoices() {
    const data = await api("/api/voice-training/voices");
    voiceList.innerHTML = "";
    const voices = data.voices || [];
    if (!voices.length) {
      const empty = document.createElement("li");
      empty.textContent = "No trained voices yet.";
      voiceList.appendChild(empty);
      return;
    }
    voices.forEach(function (voice) {
      const li = document.createElement("li");
      const info = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = voice.name || voice.slug;
      const meta = document.createElement("div");
      meta.className = "meta";
      const bits = [voice.slug, voice.language];
      if (voice.duration_s) bits.push(Number(voice.duration_s).toFixed(1) + "s");
      if (voice.source) bits.push(voice.source);
      meta.textContent = bits.filter(Boolean).join(" · ");
      info.appendChild(title);
      info.appendChild(meta);
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "Delete";
      del.addEventListener("click", function () {
        if (!window.confirm("Delete voice “" + (voice.name || voice.slug) + "”?")) return;
        api("/api/voice-training/voices/" + encodeURIComponent(voice.slug), { method: "DELETE" })
          .then(refreshVoices)
          .catch(function (err) { showError(err.message); });
      });
      li.appendChild(info);
      li.appendChild(del);
      voiceList.appendChild(li);
    });
  }

  async function pollJob(id) {
    const data = await api("/api/voice-training/jobs/" + encodeURIComponent(id));
    statusEl.hidden = false;
    statusTitle.textContent = data.stage || data.status || "Working…";
    statusBar.value = data.progress || 0;
    const selected = (data.clips || []).filter(function (c) { return c.selected; }).length;
    statusDetail.textContent = selected
      ? "Using " + selected + " scored clip(s)."
      : (data.status === "running" ? "Scoring and combining clips…" : "");
    if (data.status === "done") {
      resultEl.hidden = false;
      resultDetail.textContent = "Saved “" + (data.name || data.slug) + "” as " + data.slug +
        (data.duration_s ? " (" + Number(data.duration_s).toFixed(1) + "s reference)." : ".");
      showError("");
      refreshVoices().catch(function (err) { showError(err.message); });
      return;
    }
    if (data.status === "error") {
      showError(data.error || "Training failed.");
      return;
    }
    window.setTimeout(function () { pollJob(id).catch(function (err) { showError(err.message); }); }, 1500);
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    showError("");
    resultEl.hidden = true;
    if (!consentEl.checked) {
      showError("Consent is required: you must have this speaker's permission to clone their voice.");
      return;
    }
    const body = new FormData();
    body.append("name", (nameEl.value || "").trim());
    body.append("language", (languageEl.value || "").trim());
    body.append("consent", "true");
    body.append("seed", "42");
    Array.from(clipsEl.files || []).forEach(function (file, index) {
      body.append("clips", file, file.name);
      const area = document.getElementById("transcript-" + index);
      if (area && area.value.trim()) body.append("transcript_" + index, area.value.trim());
    });
    trainBtn.disabled = true;
    statusEl.hidden = false;
    statusTitle.textContent = "Starting training job…";
    statusBar.value = 1;
    api("/api/voice-training/jobs", { method: "POST", body: body })
      .then(function (job) { return pollJob(job.id); })
      .catch(function (err) { showError(err.message); })
      .then(function () { syncTrainEnabled(); });
  });

  clipsEl.addEventListener("change", renderClipEditors);
  nameEl.addEventListener("input", syncTrainEnabled);
  languageEl.addEventListener("input", syncTrainEnabled);
  consentEl.addEventListener("change", syncTrainEnabled);
  syncTrainEnabled();
  refreshVoices().catch(function (err) { showError(err.message); });
})();
