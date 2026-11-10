/* Visible web-UI branding only. Does not rename backend services or API paths. */
(function () {
  var NAME = "CanberraAI Voice";
  var FOOTER = "Powered by CanberraAI Voice Agent \u00b7 Hosted in Vadodara, IN";

  function applyTitle() {
    if (!document.title || document.title === "VoiceStudio" || document.title.indexOf("VoiceStudio") !== -1) {
      document.title = NAME;
    }
  }

  function isBrandNode(node) {
    if (!node || node.nodeType !== 3) return false;
    return node.nodeValue && node.nodeValue.trim() === "VoiceStudio";
  }

  function renameBrand() {
    var root = document.getElementById("root") || document.body;
    if (!root) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      if (!isBrandNode(node)) continue;
      var el = node.parentElement;
      if (!el) continue;
      // Sidebar / top-bar wordmark and aria labels — not docs, licences, or commands.
      var inBrand =
        el.closest("a[aria-label*='VoiceStudio']") ||
        el.closest("[data-slot='titlebar-row']") ||
        el.closest("[data-slot='rail-brand']") ||
        el.classList.contains("font-semibold") ||
        (el.tagName === "SPAN" && el.className && String(el.className).indexOf("font-semibold") !== -1) ||
        el.tagName === "H1";
      if (inBrand) node.nodeValue = node.nodeValue.replace("VoiceStudio", NAME);
    }
    document.querySelectorAll("[aria-label*='VoiceStudio']").forEach(function (el) {
      var label = el.getAttribute("aria-label");
      if (label) el.setAttribute("aria-label", label.replace(/VoiceStudio/g, NAME));
    });
  }

  function ensureFooter() {
    if (document.getElementById("canberra-host-footer")) return;
    var style = document.createElement("style");
    style.setAttribute("data-canberra-footer", "1");
    style.textContent =
      "body{padding-bottom:28px}" +
      "#canberra-host-footer{position:fixed;left:0;right:0;bottom:0;z-index:80;" +
      "background:rgba(12,14,18,0.94);color:#9aa3ad;font:12px/1.4 system-ui,sans-serif;" +
      "padding:6px 14px;border-top:1px solid rgba(255,255,255,0.08);text-align:center;" +
      "pointer-events:none}";
    document.head.appendChild(style);
    var footer = document.createElement("div");
    footer.id = "canberra-host-footer";
    footer.setAttribute("role", "contentinfo");
    footer.textContent = "";
    footer.appendChild(document.createTextNode(FOOTER + "  ·  "));
    var link = document.createElement("a");
    link.href = "/voice-training/";
    link.textContent = "Voice Training";
    link.style.cssText = "color:#c9d1d9;text-decoration:underline;pointer-events:auto";
    footer.appendChild(link);
    document.body.appendChild(footer);
  }

  function apply() {
    applyTitle();
    renameBrand();
    ensureFooter();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
  var observer = new MutationObserver(apply);
  observer.observe(document.documentElement, { subtree: true, childList: true, characterData: true });
})();
