"""Map words-per-minute to a target audio duration for the TTS API."""

from __future__ import annotations

import re

# CJK and similar scripts where a "word" is often a character, not a space token.
_CJK_RE = re.compile("[㐀-鿿豈-﫿぀-ヿ가-힯]")


def word_count(text: str) -> int:
    """Count words for WPM. Space-delimited when spaces exist; else CJK chars."""
    stripped = (text or "").strip()
    if not stripped:
        return 0
    tokens = stripped.split()
    if len(tokens) > 1 or (" " in stripped or "\t" in stripped or "\n" in stripped):
        return len(tokens)
    cjk = _CJK_RE.findall(stripped)
    if len(cjk) >= max(4, len(stripped) // 2):
        return max(1, len(cjk))
    return max(1, len(tokens))


def duration_from_wpm(
    text: str,
    wpm: float,
    *,
    min_s: float = 1.0,
    max_s: float = 45.0,
) -> tuple[float, int, bool]:
    """Return (duration_seconds, words, was_capped).

    The OmniVoice API accepts ``duration`` in seconds, which overrides ``speed``.
    Mapping: duration_s = words / wpm * 60.
    """
    if wpm <= 0:
        raise ValueError("wpm must be positive")
    words = word_count(text)
    if words <= 0:
        raise ValueError("text is empty")
    raw = words / float(wpm) * 60.0
    capped = raw < min_s or raw > max_s
    duration = min(max_s, max(min_s, raw))
    return round(duration, 3), words, capped
