"""The application settings model.

Every bound in the app lives here and nowhere else. Widgets read their ranges
from :data:`LIMITS` instead of hard-coding slider minimums, so a range can never
drift out of sync with what the engine actually accepts.

:class:`Settings` is frozen; :meth:`Settings.evolve` returns a new, re-validated
instance. Values arriving from disk or from a widget are clamped rather than
rejected — a corrupt setting must never stop the app from starting.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import Any, Final

ALIGNMENTS: Final = ("left", "center", "right")
UI_THEMES: Final = ("dark", "light", "system")
SPEED_MODES: Final = ("smooth", "instant")

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class Range:
    """An inclusive numeric range with a step, shared by engine and widgets."""

    minimum: float
    maximum: float
    step: float = 1.0
    default: float = 0.0

    def clamp(self, value: float) -> float:
        return min(self.maximum, max(self.minimum, value))

    def to_slider(self, value: float) -> int:
        """Map a real value onto integer slider ticks."""
        return round(self.clamp(value) / self.step)

    def from_slider(self, ticks: int) -> float:
        return self.clamp(ticks * self.step)

    @property
    def slider_minimum(self) -> int:
        return round(self.minimum / self.step)

    @property
    def slider_maximum(self) -> int:
        return round(self.maximum / self.step)


LIMITS: Final[dict[str, Range]] = {
    "speed": Range(0.2, 20.0, 0.1, 2.0),
    "font_size": Range(16, 160, 1, 48),
    "line_spacing": Range(1.0, 3.0, 0.05, 1.25),
    "bg_opacity": Range(0.0, 1.0, 0.01, 0.72),
    "focus_ratio": Range(0.15, 0.85, 0.01, 0.45),
    "countdown_secs": Range(0, 10, 1, 3),
    "mic_threshold": Range(0.002, 0.120, 0.001, 0.025),
    "ramp_tau": Range(0.05, 2.0, 0.05, 0.45),
    "margin_ratio": Range(0.02, 0.25, 0.01, 0.07),
    "target_duration": Range(0, 7200, 1, 0),
}


def _clamp(name: str, value: Any, fallback: float) -> float:
    limit = LIMITS[name]
    try:
        return limit.clamp(float(value))
    except (TypeError, ValueError):
        return limit.clamp(fallback)


def _as_bool(value: Any, fallback: bool) -> bool:
    return bool(value) if isinstance(value, (bool, int, float)) else fallback


def _as_choice(value: Any, choices: tuple[str, ...], fallback: str) -> str:
    return value if isinstance(value, str) and value in choices else fallback


def normalize_hex(value: Any, fallback: str) -> str:
    """Accept ``#rgb``/``#rrggbb`` in any case, normalise to lowercase ``#rrggbb``."""
    if not isinstance(value, str) or not _HEX_RE.match(value.strip()):
        return fallback
    text = value.strip().lower()
    if len(text) == 4:
        text = "#" + "".join(ch * 2 for ch in text[1:])
    return text


@dataclass(frozen=True)
class Settings:
    """Validated, immutable application settings."""

    # ── Playback ──────────────────────────────────────────────────────────────
    speed: float = 2.0
    countdown_secs: int = 3
    speed_mode: str = "smooth"
    ramp_tau: float = 0.45

    # ── Typography ────────────────────────────────────────────────────────────
    font_family: str = "Arial"
    font_size: int = 48
    line_spacing: float = 1.25
    alignment: str = "left"
    margin_ratio: float = 0.07

    # ── Appearance ────────────────────────────────────────────────────────────
    theme: str = "Studio Dark"
    text_color: str = "#ffffff"
    bg_color: str = "#000000"
    bg_opacity: float = 0.72
    ui_theme: str = "dark"

    # ── Reading ───────────────────────────────────────────────────────────────
    focus_ratio: float = 0.45
    word_highlight: bool = True
    mirror_x: bool = False
    mirror_y: bool = False
    touch_controls: bool = True
    show_hud: bool = True

    # ── Audio (opt-in) ────────────────────────────────────────────────────────
    mic_enabled: bool = False
    mic_threshold: float = 0.025

    # ── Global hotkeys (opt-in — installs a system-wide keyboard hook) ────────
    global_hotkeys_enabled: bool = False

    # ── Timing / rehearsal ────────────────────────────────────────────────────
    target_duration: int = 0  # seconds; 0 disables the pace badge

    # ── Display placement ─────────────────────────────────────────────────────
    prompter_screen: str = ""  # empty means "wherever the window already is"
    prompter_fullscreen: bool = False

    # ── First run ─────────────────────────────────────────────────────────────
    onboarding_done: bool = False

    def __post_init__(self) -> None:
        set_ = object.__setattr__
        set_(self, "speed", _clamp("speed", self.speed, 2.0))
        set_(self, "countdown_secs", int(_clamp("countdown_secs", self.countdown_secs, 3)))
        set_(self, "speed_mode", _as_choice(self.speed_mode, SPEED_MODES, "smooth"))
        set_(self, "ramp_tau", _clamp("ramp_tau", self.ramp_tau, 0.45))

        set_(
            self,
            "font_family",
            self.font_family
            if isinstance(self.font_family, str) and self.font_family.strip()
            else "Arial",
        )
        set_(self, "font_size", int(_clamp("font_size", self.font_size, 48)))
        set_(self, "line_spacing", _clamp("line_spacing", self.line_spacing, 1.25))
        set_(self, "alignment", _as_choice(self.alignment, ALIGNMENTS, "left"))
        set_(self, "margin_ratio", _clamp("margin_ratio", self.margin_ratio, 0.07))

        set_(self, "theme", self.theme if isinstance(self.theme, str) else "Studio Dark")
        set_(self, "text_color", normalize_hex(self.text_color, "#ffffff"))
        set_(self, "bg_color", normalize_hex(self.bg_color, "#000000"))
        set_(self, "bg_opacity", _clamp("bg_opacity", self.bg_opacity, 0.72))
        set_(self, "ui_theme", _as_choice(self.ui_theme, UI_THEMES, "dark"))

        set_(self, "focus_ratio", _clamp("focus_ratio", self.focus_ratio, 0.45))
        set_(self, "word_highlight", _as_bool(self.word_highlight, True))
        set_(self, "mirror_x", _as_bool(self.mirror_x, False))
        set_(self, "mirror_y", _as_bool(self.mirror_y, False))
        set_(self, "touch_controls", _as_bool(self.touch_controls, True))
        set_(self, "show_hud", _as_bool(self.show_hud, True))

        set_(self, "mic_enabled", _as_bool(self.mic_enabled, False))
        set_(self, "mic_threshold", _clamp("mic_threshold", self.mic_threshold, 0.025))

        set_(self, "global_hotkeys_enabled", _as_bool(self.global_hotkeys_enabled, False))

        set_(self, "target_duration", int(_clamp("target_duration", self.target_duration, 0)))

        set_(
            self,
            "prompter_screen",
            self.prompter_screen if isinstance(self.prompter_screen, str) else "",
        )
        set_(self, "prompter_fullscreen", _as_bool(self.prompter_fullscreen, False))
        set_(self, "onboarding_done", _as_bool(self.onboarding_done, False))

    # ── Derivation ────────────────────────────────────────────────────────────
    def evolve(self, **changes: Any) -> Settings:
        """Return a re-validated copy with ``changes`` applied."""
        return dataclasses.replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> Settings:
        """Build settings from untrusted data, ignoring unknown or broken keys."""
        if not isinstance(data, dict):
            return cls()
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


DEFAULT_SETTINGS: Final = Settings()

#: Presets a user can pick without opening the colour dialogs.
PROMPTER_THEMES: Final[dict[str, dict[str, Any]]] = {
    "Studio Dark": {"bg_color": "#000000", "text_color": "#ffffff", "bg_opacity": 0.72},
    "Paper Light": {"bg_color": "#f2f1ec", "text_color": "#12130f", "bg_opacity": 0.94},
    "High Contrast": {"bg_color": "#000000", "text_color": "#ffe500", "bg_opacity": 0.97},
    "Solarized": {"bg_color": "#002b36", "text_color": "#fdf6e3", "bg_opacity": 0.90},
    "Cinema Blue": {"bg_color": "#050a1e", "text_color": "#b4d7ff", "bg_opacity": 0.87},
    "Amber Night": {"bg_color": "#0d0a05", "text_color": "#ffcf7a", "bg_opacity": 0.88},
}


@dataclass(frozen=True)
class ScriptSlot:
    """A named script saved by the user."""

    name: str
    text: str
    updated_at: str = ""


@dataclass(frozen=True)
class RehearsalRun:
    """The record of one completed rehearsal, used by the timing page."""

    finished_at: str
    duration_seconds: float
    word_count: int
    chapter_seconds: tuple[tuple[str, float], ...] = field(default_factory=tuple)

    @property
    def average_wpm(self) -> int:
        if self.duration_seconds <= 0:
            return 0
        return round(self.word_count / (self.duration_seconds / 60.0))
