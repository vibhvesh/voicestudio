(function (global) {
  "use strict";

  function base() {
    const cfg = global.VOICESTUDIO_CONFIG || {};
    let value = cfg.apiBase;
    if (value && value !== "auto") {
      return String(value).replace(/\/$/, "");
    }
    const path = (global.location && global.location.pathname) || "/";
    let dir = path;
    if (/\/index\.html$/i.test(dir)) {
      dir = dir.replace(/\/index\.html$/i, "");
    } else if (/\.html$/i.test(dir)) {
      dir = dir.slice(0, dir.lastIndexOf("/"));
    } else if (dir.endsWith("/")) {
      dir = dir.slice(0, -1);
    }
    return dir;
  }

  function url(path) {
    if (path.charAt(0) !== "/") path = "/" + path;
    return base() + path;
  }

  async function getJson(path) {
    const response = await fetch(url(path), { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(await errorMessage(response));
    }
    return response.json();
  }

  function buildBody(payload) {
    const hasFile = payload.reference instanceof File && payload.reference.size > 0;
    if (hasFile) {
      const form = new FormData();
      form.set("text", payload.text);
      form.set("language", payload.language);
      form.set("wpm", String(payload.wpm));
      form.set("voice", payload.voice);
      form.set("reference", payload.reference, payload.reference.name);
      return { body: form, headers: { Accept: "application/json" } };
    }
    return {
      body: JSON.stringify({
        text: payload.text,
        language: payload.language,
        wpm: payload.wpm,
        voice: payload.voice
      }),
      headers: { "Content-Type": "application/json", Accept: "application/json" }
    };
  }

  async function createJob(payload) {
    const packed = buildBody(payload);
    const response = await fetch(url("/api/jobs"), {
      method: "POST",
      headers: packed.headers,
      body: packed.body
    });
    if (!response.ok) {
      throw new Error(await errorMessage(response));
    }
    return response.json();
  }

  async function getJob(jobId) {
    return getJson("/api/jobs/" + encodeURIComponent(jobId));
  }

  async function getJobAudio(jobId) {
    const response = await fetch(url("/api/jobs/" + encodeURIComponent(jobId) + "/audio"), {
      headers: { Accept: "audio/wav, audio/mpeg, application/json" }
    });
    if (!response.ok) {
      throw new Error(await errorMessage(response));
    }
    const blob = await response.blob();
    return {
      blob,
      contentType: response.headers.get("Content-Type") || blob.type || "audio/wav",
      audioId: response.headers.get("X-Audio-Id") || "",
      targetDuration: Number(response.headers.get("X-Target-Duration") || 0),
      wordCount: Number(response.headers.get("X-Word-Count") || 0),
      wpm: Number(response.headers.get("X-WPM") || 0),
      voice: response.headers.get("X-Voice") || "",
      language: response.headers.get("X-Language") || "",
      capped: response.headers.get("X-Capped-Duration") === "1",
      method: response.headers.get("X-Rate-Method") || "",
      jobId: response.headers.get("X-Job-Id") || jobId
    };
  }

  async function generate(payload, options) {
    const onStatus = options && options.onStatus;
    const interval = (options && options.pollIntervalMs) || 2500;
    const created = await createJob(payload);
    if (onStatus) onStatus({ status: created.status || "queued", position: created.position || 0, elapsed_s: 0, job_id: created.job_id });
    let job = created;
    while (true) {
      job = await getJob(created.job_id);
      if (onStatus) onStatus(job);
      if (job.status === "done") break;
      if (job.status === "error") {
        throw new Error(job.error || "Generation failed.");
      }
      await sleep(interval);
    }
    const audio = await getJobAudio(created.job_id);
    audio.wordCount = audio.wordCount || job.word_count;
    audio.wpm = audio.wpm || job.wpm;
    audio.language = audio.language || job.language;
    audio.voice = audio.voice || job.voice;
    audio.targetDuration = audio.targetDuration || job.target_duration_s;
    audio.method = audio.method || job.method;
    audio.audioDuration = job.audio_duration_s;
    return audio;
  }

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  async function errorMessage(response) {
    const text = await response.text();
    try {
      const data = JSON.parse(text);
      return data.error || data.detail || text || response.statusText;
    } catch (err) {
      return text || response.statusText || "Request failed";
    }
  }

  function wordCount(text) {
    const stripped = String(text || "").trim();
    if (!stripped) return 0;
    const tokens = stripped.split(/\s+/).filter(Boolean);
    if (tokens.length > 1 || /\s/.test(stripped)) return tokens.length;
    const cjk = stripped.match(/[\u3400-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]/g);
    if (cjk && cjk.length >= Math.max(4, Math.floor(stripped.length / 2))) return cjk.length;
    return tokens.length;
  }

  function durationFromWpm(text, wpm, minS, maxS) {
    const words = wordCount(text);
    if (!words || !wpm) return { duration: 0, words: 0, capped: false, generateDuration: 0 };
    const raw = (words / wpm) * 60;
    const duration = Math.min(maxS, Math.max(minS, raw));
    return { duration, words, capped: raw < minS || raw > maxS, generateDuration: duration };
  }

  function planFromWpm(text, wpm, baseline, minS, maxS) {
    const words = wordCount(text);
    if (!words || !wpm) return { duration: 0, words: 0, capped: false, generateDuration: 0, method: "" };
    const raw = (words / wpm) * 60;
    const duration = Math.min(maxS, Math.max(minS, raw));
    const method = wpm >= baseline ? "native_speed" : "atempo";
    const generateDuration = method === "atempo" ? (words / baseline) * 60 : duration;
    return { duration, words, capped: raw < minS || raw > maxS, generateDuration, method };
  }

  global.VoiceStudioAPI = {
    base, url, getJson, createJob, getJob, getJobAudio, generate,
    wordCount, durationFromWpm, planFromWpm
  };
})(window);
