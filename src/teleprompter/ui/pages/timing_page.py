"""Target duration, live pace, and what previous run-throughs actually took."""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QPushButton, QWidget

from ...core import timing
from ...core.settings import Settings
from ...core.timing import Pace
from ...theme.tokens import Palette
from ..widgets.basic import Card, label, set_variant
from ..widgets.feedback import BAND_TEXT, PaceBadge
from .base import Page


class TimingPage(Page):
    """Rehearsal support: how long the script runs, and how long it took."""

    TITLE = "Timing"
    ICON = "timing"

    def __init__(self, state, playback, parent: QWidget | None = None) -> None:
        super().__init__(state, playback, parent)

        self.content.addWidget(self._target_card())
        self.content.addWidget(self._history_card())
        self.finish()

        playback.paceChanged.connect(self.badge.set_pace)
        playback.wpmChanged.connect(self._on_wpm)
        state.scriptChanged.connect(lambda _s: self._recalculate())
        state.rehearsalsChanged.connect(self._refresh_history)

        self.sync(state.settings)

    # ── Cards ─────────────────────────────────────────────────────────────────
    def _target_card(self) -> Card:
        card = Card(
            "Slot length",
            "Enter how long you have. The pace badge then tells you, live, whether "
            "you are going to make it.",
        )

        self.target = QLineEdit()
        self.target.setPlaceholderText("e.g. 3:00  or  180")
        self.target.setAccessibleName("Target duration")
        self.target.setToolTip("Minutes and seconds, or plain seconds. Leave empty for no target.")
        self.target.editingFinished.connect(self._on_target)
        card.add_row("Target duration", self.target)

        self.required = label("—", "title")
        card.add_row(
            "Speed you need", self.required, "Words per minute required to finish on time."
        )

        self.projection = label("—", "muted", wrap=True)
        card.add_row("At the current speed", self.projection)

        self.badge = PaceBadge()
        card.add_row("Right now", self.badge, expand=False)

        clear = QPushButton("Clear target")
        clear.setAccessibleName("Clear target duration")
        clear.clicked.connect(self._clear_target)
        set_variant(clear, "ghost")
        card.add_row("", clear, expand=False)
        return card

    def _history_card(self) -> Card:
        card = Card(
            "Recent run-throughs", "Saved automatically whenever a script plays to the end."
        )
        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setMinimumHeight(150)
        self.history.setAccessibleName("Rehearsal history")
        card.add(self.history)
        return card

    # ── Reactions ─────────────────────────────────────────────────────────────
    def _on_target(self) -> None:
        text = self.target.text().strip()
        if not text:
            self.state.update_settings(target_duration=0)
            self._recalculate()
            return

        seconds = timing.parse_duration(text)
        if seconds is None:
            self.notify.emit(
                "That duration could not be read. Try 3:00, 1:30:00 or 180.", "warning"
            )
            with self.guard():
                self.target.setText(
                    timing.format_duration(self.state.settings.target_duration)
                    if self.state.settings.target_duration
                    else ""
                )
            return

        self.state.update_settings(target_duration=int(seconds))
        with self.guard():
            self.target.setText(timing.format_duration(seconds))
        self._recalculate()

    def _clear_target(self) -> None:
        self.state.update_settings(target_duration=0)
        with self.guard():
            self.target.clear()
        self._recalculate()

    def _on_wpm(self, wpm: int) -> None:
        band = timing.reading_band(wpm)
        self.projection.setText(self._projection_text(wpm, band))

    def _projection_text(self, wpm: int, band) -> str:
        total = self.playback.transport.metrics.total_px
        seconds = timing.total_seconds(total, self.state.settings.speed)
        if seconds <= 0:
            return "Add a script to see how long it runs."
        return (
            f"{timing.format_duration(seconds)} end to end  ·  "
            f"{wpm} words per minute  ·  {BAND_TEXT[band]}"
        )

    def _recalculate(self) -> None:
        target = self.state.settings.target_duration
        words = self.state.script.word_count

        if target and words:
            needed = timing.required_wpm(words, target)
            self.required.setText(f"{needed} WPM")
            band = timing.reading_band(needed)
            colour = self._band_colour(band)
            self.required.setStyleSheet(f"color: {colour};" if colour else "")
            self.required.setToolTip(f"{words} words in {timing.format_duration(target)}")
        else:
            self.required.setText("—")
            self.required.setStyleSheet("")
            self.required.setToolTip("Set a target duration to see the required pace.")

        self._on_wpm(self.playback.current_wpm())
        self.badge.set_pace(Pace.UNKNOWN if not target else self.badge_pace())

    def badge_pace(self) -> Pace:
        return timing.pace_of(
            self.playback.transport.progress,
            self.playback.transport.elapsed_seconds,
            float(self.state.settings.target_duration),
        )

    def _band_colour(self, band) -> str:
        palette = self.palette_tokens
        if palette is None:
            return ""
        return {
            timing.ReadingBand.SLOW: palette.info,
            timing.ReadingBand.COMFORTABLE: palette.success,
            timing.ReadingBand.FAST: palette.warning,
            timing.ReadingBand.TOO_FAST: palette.danger,
        }[band]

    def _refresh_history(self) -> None:
        runs = self.state.data.rehearsals
        if not runs:
            self.history.setPlainText(
                "No run-throughs recorded yet.\n\n"
                "Play a script all the way to the end and its timing lands here."
            )
            return

        blocks = []
        for run in runs:
            when = run.finished_at.replace("T", " ").replace("+00:00", " UTC")
            header = (
                f"{when}\n"
                f"  {timing.format_duration(run.duration_seconds)}"
                f"  ·  {run.word_count} words  ·  {run.average_wpm} WPM"
            )
            chapters = "\n".join(
                f"      {title}: {timing.format_duration(seconds)}"
                for title, seconds in run.chapter_seconds
            )
            blocks.append(f"{header}\n{chapters}" if chapters else header)
        self.history.setPlainText("\n\n".join(blocks))

    # ── Hooks ─────────────────────────────────────────────────────────────────
    def on_palette(self, palette: Palette, ui_font: str, mono_font: str) -> None:
        self.badge.apply_palette(palette)
        self._recalculate()

    def sync(self, settings: Settings) -> None:
        with self.guard():
            self.target.setText(
                timing.format_duration(settings.target_duration) if settings.target_duration else ""
            )
        self._recalculate()
        self._refresh_history()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._recalculate()
