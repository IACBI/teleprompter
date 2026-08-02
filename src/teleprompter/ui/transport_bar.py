"""The always-visible playback bar.

Playback used to live on one tab, which meant the operator had to navigate back
to it to stop the script. It is now pinned to the bottom of the control panel
and reachable from every page.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ..core import timing
from ..core.settings import LIMITS, Settings
from ..core.timing import Pace
from ..core.transport import PlayState
from ..resources import icons
from ..state import AppState, PlaybackController
from ..theme.stylesheet import repolish
from ..theme.tokens import MIN_HIT_TARGET, SPACE, Palette
from .widgets.basic import IconButton, Separator, label, set_variant
from .widgets.controls import LabeledSlider
from .widgets.feedback import BAND_TEXT, PaceBadge, StatChip
from .widgets.seekbar import SeekBar

_STATE_LOOK: dict[PlayState, tuple[str, str]] = {
    PlayState.IDLE: ("Play", "play"),
    PlayState.PAUSED: ("Resume", "play"),
    PlayState.PLAYING: ("Pause", "pause"),
    PlayState.COUNTDOWN: ("Cancel", "stop"),
    PlayState.FINISHED: ("Play again", "rewind"),
}


class TransportBar(QWidget):
    """Play controls, scrubber and live readouts."""

    previousChapter = Signal()
    nextChapter = Signal()

    def __init__(
        self, state: AppState, playback: PlaybackController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._playback = playback
        self._palette: Palette | None = None
        self._syncing = False

        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE.xl, SPACE.md, SPACE.xl, SPACE.md)
        column.setSpacing(SPACE.sm)

        column.addWidget(Separator())
        column.addSpacing(SPACE.xxs)

        self.seek = SeekBar()
        self.seek.seeked.connect(playback.seek_fraction)
        column.addWidget(self.seek)

        column.addLayout(self._build_controls())

        # ── Wiring ────────────────────────────────────────────────────────────
        playback.stateChanged.connect(self._on_state)
        playback.progressChanged.connect(self.seek.set_progress)
        playback.remainingChanged.connect(self._on_remaining)
        playback.elapsedChanged.connect(self._on_elapsed)
        playback.wpmChanged.connect(self._on_wpm)
        playback.paceChanged.connect(self._on_pace)
        playback.countdownChanged.connect(self._on_countdown)
        state.settingsChanged.connect(self.sync)
        state.scriptChanged.connect(lambda _s: self._refresh_marks())

        self._on_state(playback.state)
        self.sync(state.settings)

    # ── Construction ──────────────────────────────────────────────────────────
    def _build_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(SPACE.md)

        self._icon_buttons: dict[str, IconButton] = {}

        self.reset_button = IconButton("rewind", "Back to the start  (R)")
        self.reset_button.clicked.connect(self._playback.reset)
        row.addWidget(self.reset_button)
        self._icon_buttons["reset"] = self.reset_button

        self.prev_button = IconButton("skip-back", "Previous chapter  (Ctrl+Left)")
        self.prev_button.clicked.connect(self.previousChapter)
        row.addWidget(self.prev_button)
        self._icon_buttons["prev"] = self.prev_button

        self.play_button = QPushButton("Play")
        self.play_button.setMinimumHeight(MIN_HIT_TARGET + 6)
        self.play_button.setMinimumWidth(132)
        self.play_button.setAccessibleName("Play or pause")
        self.play_button.setToolTip("Play or pause  (Space)")
        self.play_button.clicked.connect(self._playback.toggle)
        set_variant(self.play_button, "primary")
        row.addWidget(self.play_button)

        self.next_button = IconButton("skip-forward", "Next chapter  (Ctrl+Right)")
        self.next_button.clicked.connect(self.nextChapter)
        row.addWidget(self.next_button)
        self._icon_buttons["next"] = self.next_button

        row.addSpacing(SPACE.md)

        self.speed = LabeledSlider(LIMITS["speed"], suffix="×", decimals=1)
        self.speed.setAccessibleName("Scroll speed")
        self.speed.setToolTip("Scroll speed — the up and down arrow keys change it too")
        self.speed.setMaximumWidth(220)
        self.speed.valueChanged.connect(self._on_speed)
        row.addWidget(label("Speed", "muted"))
        row.addWidget(self.speed, 1)

        row.addSpacing(SPACE.md)

        self.elapsed_chip = StatChip("Elapsed", "0:00")
        self.remaining_chip = StatChip("Remaining", "—")
        self.wpm_chip = StatChip("WPM", "—")
        for chip in (self.elapsed_chip, self.remaining_chip, self.wpm_chip):
            row.addWidget(chip)

        self.pace = PaceBadge()
        row.addWidget(self.pace)

        return row

    # ── Theming ───────────────────────────────────────────────────────────────
    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        for button in self._icon_buttons.values():
            button.apply_palette(palette)
        self.seek.apply_palette(palette)
        self.pace.apply_palette(palette)
        self._on_state(self._playback.state)

    # ── Reactions ─────────────────────────────────────────────────────────────
    def _on_state(self, state: PlayState) -> None:
        text, icon_name = _STATE_LOOK.get(state, _STATE_LOOK[PlayState.IDLE])
        self.play_button.setText(text)
        self.play_button.setAccessibleName(text)
        if self._palette is not None:
            self.play_button.setIcon(icons.icon(icon_name, self._palette.on_accent, 18))
            self.play_button.setIconSize(icons.icon_size(18))
        variant = "primary" if state is not PlayState.PLAYING else "accentSoft"
        if self.play_button.property("variant") != variant:
            self.play_button.setProperty("variant", variant)
            repolish(self.play_button)

    def _on_countdown(self, value) -> None:
        if value is not None:
            self.play_button.setText(f"Starting in {value}")

    def _on_remaining(self, seconds: float) -> None:
        total = self._playback.transport.metrics.total_px
        self.remaining_chip.set_value(timing.format_duration(seconds) if total else "—")

    def _on_elapsed(self, seconds: float) -> None:
        self.elapsed_chip.set_value(timing.format_duration(seconds))

    def _on_wpm(self, wpm: int) -> None:
        if wpm <= 0:
            self.wpm_chip.set_value("—")
            return
        band = timing.reading_band(wpm)
        colour = None
        if self._palette is not None:
            colour = {
                timing.ReadingBand.SLOW: self._palette.info,
                timing.ReadingBand.COMFORTABLE: self._palette.success,
                timing.ReadingBand.FAST: self._palette.warning,
                timing.ReadingBand.TOO_FAST: self._palette.danger,
            }[band]
        self.wpm_chip.set_value(str(wpm), colour)
        self.wpm_chip.setToolTip(f"{wpm} words per minute — {BAND_TEXT[band]}")

    def _on_pace(self, pace: Pace) -> None:
        self.pace.set_pace(pace)
        self.pace.setVisible(self._state.settings.target_duration > 0)

    def _on_speed(self, value: float) -> None:
        if not self._syncing:
            self._state.update_settings(speed=value)

    def _refresh_marks(self) -> None:
        script = self._state.script
        blocks = len(script.blocks)
        if blocks <= 0 or not script.chapters:
            self.seek.set_chapter_marks(())
            return
        self.seek.set_chapter_marks(
            tuple(chapter.block_index / blocks for chapter in script.chapters)
        )

    def sync(self, settings: Settings) -> None:
        self._syncing = True
        try:
            self.speed.set_value(settings.speed)
        finally:
            self._syncing = False
        self.pace.setVisible(settings.target_duration > 0)
        has_chapters = bool(self._state.script.chapters)
        self.prev_button.setEnabled(has_chapters)
        self.next_button.setEnabled(has_chapters)
        self._refresh_marks()
