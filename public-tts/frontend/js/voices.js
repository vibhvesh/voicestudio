/* Unified public voice list: saved clones first, then named style presets. */
(function (global) {
  "use strict";

  var PRESET_ORDER = [
    "narrator", "female_young", "male_young", "female_middle",
    "male_middle", "child", "elderly", "whisper"
  ];

  var PRESET_DISPLAY = {
    narrator: { label: "Priya", hint: "young female" },
    female_young: { label: "Anjali", hint: "young female" },
    male_young: { label: "Rohan", hint: "young male" },
    female_middle: { label: "Sunita", hint: "middle-aged female" },
    male_middle: { label: "Vikram", hint: "middle-aged male" },
    child: { label: "Chintu", hint: "child" },
    elderly: { label: "Dadaji", hint: "elderly" },
    whisper: { label: "Whisper", hint: "soft whisper" }
  };

  var LANGUAGE_HINTS = {
    hi: "Hindi", en: "English", es: "Spanish", fr: "French", de: "German",
    ja: "Japanese", zh: "Chinese", ar: "Arabic", arb: "Arabic", bn: "Bengali",
    ta: "Tamil", te: "Telugu", mr: "Marathi", gu: "Gujarati", pa: "Punjabi", ur: "Urdu"
  };

  function languageHint(code) {
    var value = String(code || "").trim();
    if (!value) return "saved voice";
    return LANGUAGE_HINTS[value.toLowerCase()] || value;
  }

  function presetDisplay(voice) {
    var id = voice && (voice.id || voice.slug);
    var mapped = PRESET_DISPLAY[id];
    if (mapped) return mapped;
    return {
      label: (voice && (voice.label || voice.name)) || id || "Voice",
      hint: (voice && voice.blurb) || ""
    };
  }

  function mergeLists(saved, presets, defaultId) {
    var list = [];
    var seen = {};
    var i, item, id, disp;

    saved = saved || [];
    presets = presets || [];
    defaultId = defaultId || "narrator";

    for (i = 0; i < saved.length; i++) {
      item = saved[i] || {};
      id = item.slug || item.id;
      if (!id || seen[id]) continue;
      list.push({
        id: id,
        label: item.name || item.label || id,
        hint: languageHint(item.language),
        kind: "saved"
      });
      seen[id] = true;
    }

    var byId = {};
    for (i = 0; i < presets.length; i++) {
      item = presets[i] || {};
      if (item.id) byId[item.id] = item;
    }
    for (i = 0; i < PRESET_ORDER.length; i++) {
      id = PRESET_ORDER[i];
      item = byId[id];
      if (!item || seen[id]) continue;
      disp = presetDisplay(item);
      list.push({
        id: id,
        label: disp.label + (id === defaultId ? "" : ""),
        hint: disp.hint,
        kind: "preset",
        isDefault: id === defaultId
      });
      seen[id] = true;
    }
    for (id in byId) {
      if (!Object.prototype.hasOwnProperty.call(byId, id) || seen[id]) continue;
      item = byId[id];
      disp = presetDisplay(item);
      list.push({ id: id, label: disp.label, hint: disp.hint, kind: "preset" });
      seen[id] = true;
    }
    return list;
  }

  function render(container, voices, defaultId) {
    if (!container) return;
    container.innerHTML = "";
    defaultId = defaultId || "narrator";
    var selected = defaultId;
    var ids = {};
    var i;
    for (i = 0; i < voices.length; i++) ids[voices[i].id] = true;
    if (!ids[selected] && voices.length) selected = voices[0].id;

    for (i = 0; i < voices.length; i++) {
      var voice = voices[i];
      var option = document.createElement("label");
      option.className = "voice-option";
      if (voice.isDefault || voice.id === defaultId) option.classList.add("is-default");

      var input = document.createElement("input");
      input.type = "radio";
      input.name = "voice";
      input.value = voice.id;
      input.checked = voice.id === selected;

      var text = document.createElement("span");
      text.className = "voice-text";

      var name = document.createElement("span");
      name.className = "voice-name";
      name.textContent = voice.label + (voice.id === defaultId && voice.kind === "preset" ? "" : "");
      if (voice.id === defaultId && voice.kind === "preset") {
        var def = document.createElement("span");
        def.className = "voice-default";
        def.textContent = " default";
        name.appendChild(def);
      }

      var hint = document.createElement("span");
      hint.className = "voice-hint";
      hint.textContent = voice.hint || "";

      text.appendChild(name);
      if (voice.hint) text.appendChild(hint);
      option.appendChild(input);
      option.appendChild(text);
      container.appendChild(option);
    }
  }

  function selected(container) {
    if (!container) return "narrator";
    var checked = container.querySelector('input[name="voice"]:checked');
    if (checked && checked.value) return checked.value;
    var first = container.querySelector('input[name="voice"]');
    return (first && first.value) || "narrator";
  }

  global.VoiceStudioVoices = {
    PRESET_ORDER: PRESET_ORDER,
    PRESET_DISPLAY: PRESET_DISPLAY,
    mergeLists: mergeLists,
    render: render,
    selected: selected,
    languageHint: languageHint
  };
})(window);
