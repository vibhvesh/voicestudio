"""Map a target speaking rate onto OmniVoice speed or ffmpeg atempo.

SOP tests on this host found that `duration` and `speed < 1` do not reliably
slow articulation. Faster speech uses native `speed = target / baseline`.
Slower speech is generated at speed 1.0 and then time-stretched.
The measured baseline at speed 1.0 is about 194 WPM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    """Expected output length: words / wpm * 60, capped for the UI."""
    if wpm <= 0:
        raise ValueError("wpm must be positive")
    words = word_count(text)
    if words <= 0:
        raise ValueError("text is empty")
    raw = words / float(wpm) * 60.0
    capped = raw < min_s or raw > max_s
    duration = min(max_s, max(min_s, raw))
    return round(duration, 3), words, capped


def speed_for_wpm(target_wpm: float, baseline_wpm: float) -> float:
    """Native OmniVoice speed for faster speech: target / baseline, clamped."""
    if baseline_wpm <= 0:
        raise ValueError("baseline_wpm must be positive")
    return max(0.25, min(4.0, float(target_wpm) / float(baseline_wpm)))


def atempo_for_wpm(target_wpm: float, baseline_wpm: float) -> float:
    """Time-stretch factor for slower speech: target / baseline."""
    if baseline_wpm <= 0 or target_wpm <= 0:
        raise ValueError("wpm values must be positive")
    return float(target_wpm) / float(baseline_wpm)


def atempo_chain(factor: float) -> list[float]:
    """Split a stretch factor into ffmpeg atempo stages in the 0.5–2.0 range."""
    if factor <= 0:
        raise ValueError("atempo factor must be positive")
    parts: list[float] = []
    remaining = float(factor)
    while remaining < 0.5:
        parts.append(0.5)
        remaining /= 0.5
    while remaining > 2.0:
        parts.append(2.0)
        remaining /= 2.0
    parts.append(round(remaining, 6))
    return parts


def atempo_filter(factor: float) -> str:
    return ",".join(f"atempo={part}" for part in atempo_chain(factor))


@dataclass(frozen=True)
class RatePlan:
    words: int
    target_wpm: float
    baseline_wpm: float
    method: str
    api_speed: float
    atempo: float | None
    atempo_filter: str | None
    expected_duration_s: float
    generate_duration_s: float
    capped: bool


def plan_rate(
    text: str,
    target_wpm: float,
    *,
    baseline_wpm: float = 194.0,
    min_s: float = 1.0,
    max_s: float = 45.0,
) -> RatePlan:
    """Choose native speed (faster) or atempo (slower) for a target WPM."""
    if target_wpm <= 0:
        raise ValueError("wpm must be positive")
    words = word_count(text)
    if words <= 0:
        raise ValueError("text is empty")
    expected_raw = words / float(target_wpm) * 60.0
    capped = expected_raw < min_s or expected_raw > max_s
    expected = min(max_s, max(min_s, expected_raw))
    if target_wpm >= baseline_wpm:
        speed = speed_for_wpm(target_wpm, baseline_wpm)
        generate_s = expected
        return RatePlan(
            words=words,
            target_wpm=float(target_wpm),
            baseline_wpm=float(baseline_wpm),
            method="native_speed",
            api_speed=speed,
            atempo=None,
            atempo_filter=None,
            expected_duration_s=round(expected, 3),
            generate_duration_s=round(generate_s, 3),
            capped=capped,
        )
    factor = atempo_for_wpm(target_wpm, baseline_wpm)
    # Generate at the natural rate, then stretch; wait time follows the unstretched clip.
    generate_s = words / float(baseline_wpm) * 60.0
    return RatePlan(
        words=words,
        target_wpm=float(target_wpm),
        baseline_wpm=float(baseline_wpm),
        method="atempo",
        api_speed=1.0,
        atempo=factor,
        atempo_filter=atempo_filter(factor),
        expected_duration_s=round(expected, 3),
        generate_duration_s=round(generate_s, 3),
        capped=capped,
    )
