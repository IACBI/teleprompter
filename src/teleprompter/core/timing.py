"""Speed, pace and duration mathematics.

Scroll speed is expressed in **pixels per reference frame** at 60 fps, which is
the unit the UI slider has always shown. Everything else derives from that:

    px/second = speed × 60
    px/minute = speed × 3600
"""

from __future__ import annotations

import math
from enum import Enum

#: Duration of one reference frame at 60 fps, in milliseconds.
FRAME_MS = 1000.0 / 60.0

#: Reading speeds a broadcaster would recognise, in words per minute.
WPM_SLOW = 100
WPM_COMFORTABLE = 160
WPM_FAST = 220
WPM_TOO_FAST = 280


class Pace(Enum):
    """How the current run compares with the target duration."""

    AHEAD = "ahead"
    ON_TRACK = "on_track"
    BEHIND = "behind"
    UNKNOWN = "unknown"


class ReadingBand(Enum):
    """Qualitative bucket for a words-per-minute figure."""

    SLOW = "slow"
    COMFORTABLE = "comfortable"
    FAST = "fast"
    TOO_FAST = "too_fast"


def pixels_per_second(speed: float) -> float:
    """Convert the UI speed unit to pixels per second."""
    return speed * (1000.0 / FRAME_MS)


def speed_for_pixels_per_second(px_per_second: float) -> float:
    """Inverse of :func:`pixels_per_second`."""
    return px_per_second * FRAME_MS / 1000.0


def estimate_wpm(word_count: int, speed: float, total_px: float) -> int:
    """Words per minute implied by scrolling ``total_px`` at ``speed``."""
    if total_px <= 0 or word_count <= 0 or speed <= 0:
        return 0
    px_per_minute = pixels_per_second(speed) * 60.0
    return round(px_per_minute * (word_count / total_px))


def speed_for_wpm(word_count: int, total_px: float, target_wpm: float) -> float:
    """Scroll speed that would read ``word_count`` words at ``target_wpm``."""
    if word_count <= 0 or total_px <= 0 or target_wpm <= 0:
        return 0.0
    px_per_minute = target_wpm * (total_px / word_count)
    return speed_for_pixels_per_second(px_per_minute / 60.0)


def total_seconds(total_px: float, speed: float) -> float:
    """How long a full run takes at a constant ``speed``."""
    if speed <= 0 or total_px <= 0:
        return 0.0
    return total_px / pixels_per_second(speed)


def remaining_seconds(scroll_y: float, total_px: float, speed: float) -> float:
    """Seconds left at the current constant ``speed``."""
    if speed <= 0 or total_px <= 0:
        return 0.0
    return max(0.0, total_px - scroll_y) / pixels_per_second(speed)


def speed_for_duration(total_px: float, target_seconds: float) -> float:
    """Scroll speed that finishes ``total_px`` in exactly ``target_seconds``."""
    if target_seconds <= 0 or total_px <= 0:
        return 0.0
    return speed_for_pixels_per_second(total_px / target_seconds)


def required_wpm(word_count: int, target_seconds: float) -> int:
    """Words per minute needed to deliver ``word_count`` words on time."""
    if word_count <= 0 or target_seconds <= 0:
        return 0
    return round(word_count / (target_seconds / 60.0))


def reading_band(wpm: int) -> ReadingBand:
    """Bucket a WPM figure for colour/label purposes."""
    if wpm < WPM_SLOW:
        return ReadingBand.SLOW
    if wpm < WPM_FAST:
        return ReadingBand.COMFORTABLE
    if wpm < WPM_TOO_FAST:
        return ReadingBand.FAST
    return ReadingBand.TOO_FAST


def pace_of(
    progress: float, elapsed_seconds: float, target_seconds: float, tolerance: float = 0.03
) -> Pace:
    """Compare actual progress with where the run should be by now.

    ``progress`` is 0.0–1.0. ``tolerance`` is the fraction of the target duration
    that still counts as on track, so a rounding wobble doesn't flip the badge.
    """
    if target_seconds <= 0 or elapsed_seconds <= 0:
        return Pace.UNKNOWN
    expected = min(1.0, elapsed_seconds / target_seconds)
    delta = progress - expected
    if delta > tolerance:
        return Pace.AHEAD
    if delta < -tolerance:
        return Pace.BEHIND
    return Pace.ON_TRACK


def ramp(current: float, target: float, dt_seconds: float, tau_seconds: float) -> float:
    """Exponentially approach ``target``.

    ``tau_seconds`` is the time constant: after one tau roughly 63% of the gap is
    closed. A tau of zero snaps immediately, which is what "instant" speed mode
    uses.
    """
    if tau_seconds <= 0 or dt_seconds <= 0:
        return target
    factor = math.exp(-dt_seconds / tau_seconds)
    value = target + (current - target) * factor
    # Settle exactly on target once the remaining gap is imperceptible.
    return target if abs(value - target) < 1e-4 else value


def format_duration(seconds: float) -> str:
    """Format seconds as ``M:SS`` or ``H:MM:SS``."""
    if seconds < 0 or not math.isfinite(seconds):
        return "—"
    total = round(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def parse_duration(text: str) -> float | None:
    """Parse ``"90"``, ``"1:30"`` or ``"1:02:03"`` into seconds."""
    parts = text.strip().split(":")
    if not parts or any(not p.strip().isdigit() for p in parts) or len(parts) > 3:
        return None
    values = [int(p) for p in parts]
    seconds = 0.0
    for value in values:
        seconds = seconds * 60 + value
    return seconds
