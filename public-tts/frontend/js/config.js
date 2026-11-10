/* VoiceStudio Speak frontend configuration.
 *
 * apiBase is prepended to every API path. The frontend always builds URLs as:
 *   apiBase + "/api/..."
 * including the audio fetch, e.g. apiBase + "/api/jobs/" + id + "/audio".
 *
 * Values:
 *   "" or "auto"  — when this page is served from the proxy root
 *                   (http://130.250.191.136:8788/), "auto" becomes "".
 *                   If the page is under /speak/, "auto" becomes "/speak".
 *   "/voice"      — for https://bowlinger.net/voice/ (static files there,
 *                   /voice/api/* proxied to the VPS /api/*).
 *
 * Do not put the VoiceStudio API key in this file.
 */
window.VOICESTUDIO_CONFIG = window.VOICESTUDIO_CONFIG || {
  apiBase: "auto"
};
