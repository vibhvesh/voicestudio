(function (global) {
  "use strict";

  function base() {
    const cfg = global.VOICESTUDIO_CONFIG || {};
    return String(cfg.apiBase || "").replace(/\/$/, "");
  }

  function url(path) {
    return base() + path;
  }

  async function getJson(path) {
    const response = await fetch(url(path), { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(await errorMessage(response));
    }
    return response.json();
  }

  async function generate(payload) {
    const hasFile = payload.reference instanceof File && payload.reference.size > 0;
    let response;
    if (hasFile) {
      const form = new FormData();
      form.set("text", payload.text);
      form.set("language", payload.language);
      form.set("wpm", String(payload.wpm));
      form.set("voice", payload.voice);
      form.set("reference", payload.reference, payload.reference.name);
      response = await fetch(url("/api/generate"), { method: "POST", body: form });
    } else {
      response = await fetch(url("/api/generate"), {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "audio/wav, application/json" },
        body: JSON.stringify({
          text: payload.text,
          language: payload.language,
          wpm: payload.wpm,
          voice: payload.voice
        })
      });
    }
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
      wpm: Number(response.headers.get("X-WPM") || payload.wpm),
      voice: response.headers.get("X-Voice") || payload.voice,
      language: response.headers.get("X-Language") || payload.language,
      capped: response.headers.get("X-Capped-Duration") === "1"
    };
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
    if (!words || !wpm) return { duration: 0, words: 0, capped: false };
    const raw = (words / wpm) * 60;
    const duration = Math.min(maxS, Math.max(minS, raw));
    return { duration, words, capped: raw < minS || raw > maxS };
  }

  global.VoiceStudioAPI = { base, url, getJson, generate, wordCount, durationFromWpm };
})(window);
