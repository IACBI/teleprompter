"""Voice-activated scrolling.

Off by default, and the page says plainly what the microphone is used for.
"""

from __future__ import annotations

from PySide6.QtWidgets import QProgressBar, QWidget

from ...core.settings import LIMITS, Settings
from ...services.audio import AUDIO_AVAILABLE
from ...theme.tokens import Palette
from ..widgets.basic import Card, label
from ..widgets.controls import LabeledSlider, ToggleSwitch
from .base import Page

PRIVACY_NOTE = (
    "Audio is measured for loudness only, on this computer. Nothing is recorded, "
    "written to disk or sent anywhere, and the microphone is released the moment "
    "you switch this off."
)

UNAVAILABLE_NOTE = (
    "Voice detection needs two extra packages.\n\nInstall them with:  pip install sounddevice numpy"
)


class AudioPage(Page):
    """Microphone-driven pausing."""

    TITLE = "Voice"
    ICON = "mic"

    def __init__(self, state, playback, parent: QWidget | None = None) -> None:
        super().__init__(state, playback, parent)

        self._toggle: ToggleSwitch | None = None
        self.content.addWidget(self._card())
        self.finish()
        self.sync(state.settings)

    def _card(self) -> Card:
        card = Card(
            "Pause when you stop speaking",
            "The script waits during a pause for breath and picks up when you carry on.",
        )

        if not AUDIO_AVAILABLE:
            card.add(label(UNAVAILABLE_NOTE, "muted", wrap=True))
            return card

        self._toggle = ToggleSwitch()
        self._toggle.toggled.connect(lambda checked: self._set(mic_enabled=checked))
        card.add_row("Voice detection", self._toggle, expand=False)

        self.threshold = LabeledSlider(
            LIMITS["mic_threshold"],
            decimals=3,
            formatter=lambda v: f"{v:.3f}",
        )
        self.threshold.valueChanged.connect(lambda v: self._set(mic_threshold=v))
        card.add_row(
            "Sensitivity",
            self.threshold,
            "Lower values react to a quieter voice. Raise it in a noisy room.",
        )

        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setTextVisible(False)
        self.meter.setAccessibleName("Microphone level")
        self.meter.setToolTip("Live input level — speak to see it move")
        card.add_row("Input level", self.meter)

        self.status = label("Off", "caption")
        card.add_row("Status", self.status)

        card.add(label(PRIVACY_NOTE, "caption", wrap=True))
        return card

    # ── External updates ──────────────────────────────────────────────────────
    def set_level(self, level: float) -> None:
        if AUDIO_AVAILABLE:
            self.meter.setValue(int(min(1.0, level * 12.0) * 100))

    def set_status(self, text: str) -> None:
        if AUDIO_AVAILABLE:
            self.status.setText(text)

    def _set(self, **changes) -> None:
        if not self.syncing:
            self.state.update_settings(**changes)

    def on_palette(self, palette: Palette, ui_font: str, mono_font: str) -> None:
        if self._toggle is not None:
            self._toggle.apply_palette(palette)

    def sync(self, settings: Settings) -> None:
        if not AUDIO_AVAILABLE or self._toggle is None:
            return
        with self.guard():
            self._toggle.setChecked(settings.mic_enabled)
            self.threshold.set_value(settings.mic_threshold)
        self.threshold.setEnabled(settings.mic_enabled)
        self.meter.setEnabled(settings.mic_enabled)
        if not settings.mic_enabled:
            self.meter.setValue(0)
            self.status.setText("Off")
