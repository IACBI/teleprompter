from __future__ import annotations

import pytest

from teleprompter.core.settings import LIMITS, Range, Settings, normalize_hex


def test_defaults_are_valid():
    settings = Settings()
    assert settings.speed == pytest.approx(2.0)
    assert settings.alignment == "left"


def test_global_hotkeys_are_off_by_default():
    # Installing a system-wide keyboard hook must be a deliberate choice.
    assert Settings().global_hotkeys_enabled is False


def test_microphone_is_off_by_default():
    assert Settings().mic_enabled is False


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("speed", 1e9, LIMITS["speed"].maximum),
        ("speed", -5, LIMITS["speed"].minimum),
        ("font_size", 4, LIMITS["font_size"].minimum),
        ("font_size", 5000, LIMITS["font_size"].maximum),
        ("bg_opacity", 4.2, 1.0),
        ("bg_opacity", -1.0, 0.0),
        ("countdown_secs", 99, 10),
        ("focus_ratio", 0.0, LIMITS["focus_ratio"].minimum),
    ],
)
def test_out_of_range_values_are_clamped(field, value, expected):
    settings = Settings(**{field: value})
    assert getattr(settings, field) == pytest.approx(expected)


@pytest.mark.parametrize("value", ["sideways", "", None, 7])
def test_invalid_alignment_falls_back_to_left(value):
    assert Settings(alignment=value).alignment == "left"


def test_garbage_numbers_fall_back_instead_of_raising():
    assert Settings(speed="not a number").speed == pytest.approx(2.0)
    assert Settings(font_size=None).font_size == 48


def test_blank_font_family_falls_back():
    assert Settings(font_family="   ").font_family == "Arial"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("#FFF", "#ffffff"), ("#AbCdEf", "#abcdef"), ("  #000  ", "#000000")],
)
def test_hex_colours_are_normalised(value, expected):
    assert normalize_hex(value, "#123456") == expected


@pytest.mark.parametrize("value", ["red", "#12345", "", None, "#gggggg"])
def test_invalid_hex_falls_back(value):
    assert normalize_hex(value, "#123456") == "#123456"


def test_evolve_revalidates():
    settings = Settings().evolve(speed=999)
    assert settings.speed == LIMITS["speed"].maximum


def test_settings_are_immutable():
    with pytest.raises(Exception):
        Settings().speed = 5  # type: ignore[misc]


def test_round_trip_through_a_dict():
    original = Settings(speed=3.5, alignment="center", mirror_y=True, font_size=72)
    assert Settings.from_dict(original.to_dict()) == original


def test_from_dict_ignores_unknown_keys():
    settings = Settings.from_dict({"speed": 4.0, "colour_of_the_sky": "blue"})
    assert settings.speed == pytest.approx(4.0)


@pytest.mark.parametrize("payload", [None, [], "text", 42])
def test_from_dict_survives_junk(payload):
    assert Settings.from_dict(payload) == Settings()


def test_range_maps_to_and_from_slider_ticks():
    speed = LIMITS["speed"]
    assert speed.from_slider(speed.to_slider(3.7)) == pytest.approx(3.7, abs=speed.step)


def test_range_slider_bounds_are_integers():
    line_spacing = LIMITS["line_spacing"]
    assert line_spacing.slider_minimum == 20
    assert line_spacing.slider_maximum == 60


def test_range_clamps():
    r = Range(0.0, 10.0, 0.5)
    assert r.clamp(-1) == 0.0
    assert r.clamp(99) == 10.0
