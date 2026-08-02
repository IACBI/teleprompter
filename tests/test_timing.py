from __future__ import annotations

import pytest

from teleprompter.core.timing import (
    Pace,
    ReadingBand,
    estimate_wpm,
    format_duration,
    pace_of,
    parse_duration,
    pixels_per_second,
    ramp,
    reading_band,
    remaining_seconds,
    speed_for_duration,
    speed_for_wpm,
    total_seconds,
)


def test_speed_unit_is_pixels_per_60fps_frame():
    assert pixels_per_second(1.0) == pytest.approx(60.0)
    assert pixels_per_second(2.5) == pytest.approx(150.0)


def test_wpm_is_dimensionally_consistent():
    # 36000 px at 60 px/s takes 600 s = 10 minutes; 1000 words in 10 minutes
    # is 100 words per minute.
    assert estimate_wpm(word_count=1000, speed=1.0, total_px=36000) == 100


def test_wpm_scales_linearly_with_speed():
    slow = estimate_wpm(500, 1.0, 10000)
    fast = estimate_wpm(500, 2.0, 10000)
    assert fast == pytest.approx(slow * 2, rel=0.01)


@pytest.mark.parametrize(
    ("words", "speed", "total"),
    [(0, 2.0, 100.0), (100, 0.0, 100.0), (100, 2.0, 0.0), (100, 2.0, -5.0)],
)
def test_wpm_degenerate_inputs_return_zero(words, speed, total):
    assert estimate_wpm(words, speed, total) == 0


def test_speed_for_wpm_round_trips():
    speed = speed_for_wpm(word_count=800, total_px=24000, target_wpm=150)
    assert estimate_wpm(800, speed, 24000) == pytest.approx(150, abs=1)


def test_total_and_remaining_seconds_agree_at_the_start():
    assert remaining_seconds(0.0, 6000.0, 2.0) == pytest.approx(total_seconds(6000.0, 2.0))


def test_remaining_seconds_never_goes_negative():
    assert remaining_seconds(9999.0, 100.0, 2.0) == 0.0


def test_speed_for_duration_hits_the_target():
    speed = speed_for_duration(total_px=12000, target_seconds=120)
    assert total_seconds(12000, speed) == pytest.approx(120, rel=1e-6)


@pytest.mark.parametrize(
    ("wpm", "band"),
    [
        (40, ReadingBand.SLOW),
        (99, ReadingBand.SLOW),
        (160, ReadingBand.COMFORTABLE),
        (219, ReadingBand.COMFORTABLE),
        (250, ReadingBand.FAST),
        (400, ReadingBand.TOO_FAST),
    ],
)
def test_reading_bands(wpm, band):
    assert reading_band(wpm) is band


def test_pace_is_unknown_without_a_target():
    assert pace_of(0.5, 30.0, 0.0) is Pace.UNKNOWN


def test_pace_detects_ahead_and_behind():
    assert pace_of(progress=0.60, elapsed_seconds=50, target_seconds=100) is Pace.AHEAD
    assert pace_of(progress=0.30, elapsed_seconds=50, target_seconds=100) is Pace.BEHIND
    assert pace_of(progress=0.50, elapsed_seconds=50, target_seconds=100) is Pace.ON_TRACK


def test_pace_tolerance_absorbs_small_wobble():
    assert pace_of(progress=0.52, elapsed_seconds=50, target_seconds=100) is Pace.ON_TRACK


def test_ramp_with_zero_tau_snaps_immediately():
    assert ramp(0.0, 5.0, dt_seconds=0.016, tau_seconds=0.0) == 5.0


def test_ramp_approaches_the_target_monotonically():
    value = 0.0
    for _ in range(200):
        previous = value
        value = ramp(value, 4.0, dt_seconds=0.016, tau_seconds=0.3)
        assert value >= previous
        assert value <= 4.0
    assert value == pytest.approx(4.0, abs=1e-3)


def test_ramp_settles_exactly_on_target():
    assert ramp(3.9999999, 4.0, 0.016, 0.3) == 4.0


def test_ramp_decelerates_too():
    assert ramp(10.0, 0.0, dt_seconds=0.1, tau_seconds=0.2) < 10.0


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "0:00"), (5, "0:05"), (65, "1:05"), (600, "10:00"), (3723, "1:02:03")],
)
def test_duration_formatting(seconds, text):
    assert format_duration(seconds) == text


def test_negative_duration_shows_a_dash():
    assert format_duration(-1) == "—"


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("90", 90), ("1:30", 90), ("1:02:03", 3723), (" 2:00 ", 120)],
)
def test_duration_parsing(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize("text", ["", "abc", "1:2:3:4", "-5", "1.5"])
def test_invalid_durations_return_none(text):
    assert parse_duration(text) is None
