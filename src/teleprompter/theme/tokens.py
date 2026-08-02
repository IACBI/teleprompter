"""Design tokens.

The look is broadcast-desk: deep neutral greys, generous negative space, and a
single amber accent — the colour teleprompter operators have been reading off
glass for decades. Colour is reserved for meaning, so status green and alert red
appear only where they say something.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Palette:
    """A complete colour set for one interface theme."""

    name: str
    is_dark: bool

    # Surfaces, from furthest back to closest to the user.
    bg: str
    surface: str
    surface_raised: str
    surface_overlay: str

    # Lines.
    border: str
    border_strong: str

    # Type, from most to least prominent.
    text: str
    text_muted: str
    text_subtle: str
    text_disabled: str

    # The single accent.
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    on_accent: str

    # Meaning-carrying colours.
    success: str
    warning: str
    danger: str
    info: str

    # Selection and shadow.
    selection: str
    on_selection: str
    shadow: str


DARK: Final = Palette(
    name="dark",
    is_dark=True,
    bg="#0e0f12",
    surface="#16181d",
    surface_raised="#1e2128",
    surface_overlay="#262a33",
    border="#262b34",
    border_strong="#3a4150",
    text="#e9ebef",
    text_muted="#9aa2af",
    text_subtle="#6b7280",
    text_disabled="#4b515c",
    accent="#ffb020",
    accent_hover="#ffc24d",
    accent_pressed="#e39400",
    accent_soft="rgba(255, 176, 32, 0.16)",
    on_accent="#1a1206",
    success="#3dd68c",
    warning="#ffb020",
    danger="#f1614b",
    info="#4c9aff",
    selection="rgba(255, 176, 32, 0.28)",
    on_selection="#ffffff",
    shadow="rgba(0, 0, 0, 0.55)",
)

LIGHT: Final = Palette(
    name="light",
    is_dark=False,
    bg="#f3f4f6",
    surface="#ffffff",
    surface_raised="#ffffff",
    surface_overlay="#eaecf0",
    border="#dfe3e9",
    border_strong="#bcc3ce",
    text="#14161a",
    text_muted="#525c6b",
    text_subtle="#79828f",
    text_disabled="#a8b0bb",
    accent="#b56b00",
    accent_hover="#c97a00",
    accent_pressed="#9a5b00",
    accent_soft="rgba(181, 107, 0, 0.12)",
    on_accent="#ffffff",
    success="#12855a",
    warning="#a86400",
    danger="#c33a26",
    info="#1662cc",
    selection="rgba(181, 107, 0, 0.22)",
    on_selection="#14161a",
    shadow="rgba(20, 22, 26, 0.18)",
)


def palette_for(ui_theme: str, system_prefers_dark: bool = True) -> Palette:
    """Resolve a settings value (``dark`` / ``light`` / ``system``) to a palette."""
    if ui_theme == "light":
        return LIGHT
    if ui_theme == "dark":
        return DARK
    return DARK if system_prefers_dark else LIGHT


@dataclass(frozen=True)
class Spacing:
    """A 4-point spacing scale. Nothing in the UI uses a value outside it."""

    xxs: int = 2
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32
    huge: int = 48


@dataclass(frozen=True)
class Radii:
    sm: int = 6
    md: int = 10
    lg: int = 14
    xl: int = 20
    pill: int = 999


@dataclass(frozen=True)
class TypeScale:
    """Font sizes in logical pixels, roughly a 1.2 ratio."""

    caption: int = 11
    small: int = 12
    body: int = 13
    body_large: int = 15
    title: int = 18
    heading: int = 22
    display: int = 30
    hero: int = 44

    weight_regular: int = 400
    weight_medium: int = 500
    weight_semibold: int = 600
    weight_bold: int = 700


@dataclass(frozen=True)
class Motion:
    """Animation durations in milliseconds."""

    instant: int = 90
    fast: int = 140
    base: int = 200
    slow: int = 300
    #: Long enough to notice, short enough not to wait for.
    toast: int = 4000


SPACE: Final = Spacing()
RADIUS: Final = Radii()
TYPE: Final = TypeScale()
MOTION: Final = Motion()

#: Minimum interactive size. Anything a finger or a hurried hand has to hit is
#: at least this tall.
MIN_HIT_TARGET: Final = 32
MIN_TOUCH_TARGET: Final = 44

#: The UI font stack, in preference order. Resolved at runtime against the
#: fonts actually installed.
UI_FONT_CANDIDATES: Final = (
    "Inter",
    "Segoe UI Variable Text",
    "Segoe UI",
    "SF Pro Text",
    "Ubuntu",
    "Noto Sans",
    "DejaVu Sans",
)

MONO_FONT_CANDIDATES: Final = (
    "JetBrains Mono",
    "Cascadia Mono",
    "Consolas",
    "SF Mono",
    "DejaVu Sans Mono",
    "Menlo",
)
