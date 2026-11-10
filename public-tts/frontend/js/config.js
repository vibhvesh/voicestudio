/* VoiceStudio Speak frontend configuration.
 *
 * apiBase is the origin of the public proxy (no trailing slash).
 * Leave it empty when this page is served by the VoiceStudio proxy itself,
 * or when https://bowlinger.net reverse-proxies /voice (or the whole host)
 * to http://130.250.191.136:8788. Same-origin is the recommended setup
 * because an HTTPS page cannot call a plain HTTP API (mixed content).
 *
 * For a temporary HTTP-only test you may set:
 *   apiBase: "http://130.250.191.136:8788"
 */
window.VOICESTUDIO_CONFIG = window.VOICESTUDIO_CONFIG || {
  apiBase: ""
};
