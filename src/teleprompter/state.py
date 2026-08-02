"""Application state and the playback controller.

Every window in the app reads from exactly one :class:`AppState` and one
:class:`PlaybackController`, and talks to them through Qt signals. Nothing
reaches into another window's attributes, which is what makes it possible to
add a second prompter screen or a new page without rewiring the ones that exist.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer, Signal

from .core import timing
from .core.script import Script, parse_script
from .core.settings import PROMPTER_THEMES, RehearsalRun, Settings
from .core.transport import PlayState, Transport
from .storage import store
from .storage.store import AppData

log = logging.getLogger(__name__)

#: Nominal tick interval. Real elapsed time is measured, so this only sets how
#: often we *try* to draw, never how far the script moves.
TICK_INTERVAL_MS = 16

#: Progress, WPM and pace update far slower than the scroll — no reason to
#: churn six labels sixty times a second.
READOUT_INTERVAL_MS = 120


class AppState(QObject):
    """Settings, the current script, and everything that persists."""

    settingsChanged = Signal(Settings)
    scriptChanged = Signal(Script)
    slotsChanged = Signal()
    rehearsalsChanged = Signal()

    def __init__(self, data: AppData | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data = data or AppData()
        self._script: Script = parse_script(self._data.last_text)

    # ── Access ────────────────────────────────────────────────────────────────
    @property
    def settings(self) -> Settings:
        return self._data.settings

    @property
    def script(self) -> Script:
        return self._script

    @property
    def script_text(self) -> str:
        return self._data.last_text

    @property
    def data(self) -> AppData:
        return self._data

    # ── Mutation ──────────────────────────────────────────────────────────────
    def update_settings(self, **changes: Any) -> Settings:
        """Apply validated changes and notify listeners if anything moved."""
        current = self._data.settings
        updated = current.evolve(**changes)
        if updated == current:
            return current
        self._data.settings = updated
        self.settingsChanged.emit(updated)
        return updated

    def apply_prompter_theme(self, name: str) -> Settings:
        """Switch prompter colours to a named preset."""
        preset = PROMPTER_THEMES.get(name)
        if preset is None:
            return self._data.settings
        return self.update_settings(theme=name, **preset)

    def set_script_text(self, text: str) -> None:
        if text == self._data.last_text:
            return
        self._data.last_text = text
        self._script = parse_script(text)
        self.scriptChanged.emit(self._script)

    # ── Slots ─────────────────────────────────────────────────────────────────
    def save_slot(self, name: str, text: str) -> bool:
        if not self._data.save_slot(name, text):
            return False
        self.slotsChanged.emit()
        return True

    def delete_slot(self, name: str) -> bool:
        if not self._data.delete_slot(name):
            return False
        self.slotsChanged.emit()
        return True

    def slot_text(self, name: str) -> str | None:
        slot = self._data.slots.get(name)
        return slot.text if slot else None

    def slot_names(self) -> list[str]:
        return sorted(self._data.slots)

    def remember_file(self, path: str) -> None:
        self._data.remember_file(path)

    def add_rehearsal(self, run: RehearsalRun) -> None:
        self._data.add_rehearsal(run)
        self.rehearsalsChanged.emit()

    def reset_settings(self) -> Settings:
        """Restore factory settings, keeping scripts and slots untouched."""
        keep = self._data.settings
        self._data.settings = Settings(onboarding_done=keep.onboarding_done)
        self.settingsChanged.emit(self._data.settings)
        return self._data.settings

    # ── Persistence ───────────────────────────────────────────────────────────
    def save(self) -> str | None:
        """Persist state. Returns an error message on failure, else None."""
        try:
            store.save(self._data)
        except OSError as exc:
            log.exception("Could not save application state")
            return f"Your work could not be saved to disk.\n\n{exc}"
        return None


class PlaybackController(QObject):
    """Drives the pure :class:`Transport` from Qt's event loop."""

    stateChanged = Signal(PlayState)
    positionChanged = Signal(float)  # scroll_y in pixels
    progressChanged = Signal(float)  # 0.0 – 1.0
    countdownChanged = Signal(object)  # int | None
    wpmChanged = Signal(int)
    remainingChanged = Signal(float)  # seconds
    elapsedChanged = Signal(float)  # seconds
    paceChanged = Signal(object)  # timing.Pace
    pausedAtMarker = Signal()
    finished = Signal()
    repaintRequested = Signal()

    def __init__(self, state: AppState, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self.transport = Transport()
        self._gate = 1.0
        self._word_count = state.script.word_count
        self._chapter_marks: list[tuple[str, float]] = []
        self._chapter_started_at = 0.0
        self._current_chapter = ""

        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

        self._readout = QTimer(self)
        self._readout.setInterval(READOUT_INTERVAL_MS)
        self._readout.timeout.connect(self._emit_readouts)

        state.scriptChanged.connect(self._on_script_changed)

    # ── Queries ───────────────────────────────────────────────────────────────
    @property
    def state(self) -> PlayState:
        return self.transport.state

    @property
    def is_playing(self) -> bool:
        return self.transport.is_playing

    @property
    def scroll_y(self) -> float:
        return self.transport.scroll_y

    @property
    def countdown_value(self) -> int | None:
        return self.transport.countdown_value

    def current_wpm(self) -> int:
        return timing.estimate_wpm(
            self._word_count,
            self._state.settings.speed,
            self.transport.metrics.total_px,
        )

    # ── Layout coupling ───────────────────────────────────────────────────────
    def set_metrics(self, total_px: float, line_height: int, pause_lines: frozenset[int]) -> None:
        """Told by the prompter window whenever the script re-flows."""
        self.transport.set_metrics(total_px, line_height, pause_lines)
        self._emit_readouts()

    # ── Commands ──────────────────────────────────────────────────────────────
    def toggle(self) -> None:
        if self.transport.state.is_active:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        if self.transport.state is PlayState.PLAYING:
            return
        starting_fresh = self.transport.scroll_y <= 0.0 or self.transport.at_end
        if self.transport.start(self._state.settings.countdown_secs):
            if starting_fresh:
                self._begin_rehearsal()
            self._clock.restart()
            self._timer.start()
            self._readout.start()
            self._announce()

    def pause(self) -> None:
        if self.transport.pause():
            self._stop_clocks()
            self._announce()

    def reset(self) -> None:
        self.transport.reset()
        self._stop_clocks()
        self._chapter_marks.clear()
        self._current_chapter = ""
        self._announce()
        self.positionChanged.emit(0.0)
        self._emit_readouts()
        self.repaintRequested.emit()

    def seek_pixels(self, delta: float) -> None:
        if self.transport.seek_pixels(delta):
            self.positionChanged.emit(self.transport.scroll_y)
            self._emit_readouts()
            self.repaintRequested.emit()

    def seek_to_line(self, line_index: int) -> None:
        if self.transport.seek_to_line(line_index):
            self.positionChanged.emit(self.transport.scroll_y)
            self._emit_readouts()
            self.repaintRequested.emit()

    def seek_fraction(self, fraction: float) -> None:
        target = self.transport.metrics.total_px * max(0.0, min(1.0, fraction))
        if self.transport.seek_to(target):
            self.positionChanged.emit(self.transport.scroll_y)
            self._emit_readouts()
            self.repaintRequested.emit()

    def set_gate(self, gate: float) -> None:
        """Voice-activated scrolling multiplier, 0.0 – 1.0."""
        self._gate = max(0.0, min(1.0, gate))

    # ── Clock ─────────────────────────────────────────────────────────────────
    def _tick(self) -> None:
        settings = self._state.settings
        tau = settings.ramp_tau if settings.speed_mode == "smooth" else 0.0
        gate = self._gate if settings.mic_enabled else 1.0

        result = self.transport.tick(
            self._clock.restart(),
            settings.speed,
            ramp_tau=tau,
            gate=gate,
        )

        if result.countdown_changed:
            self.countdownChanged.emit(self.transport.countdown_value)
        if result.moved:
            self.positionChanged.emit(self.transport.scroll_y)
        if result.paused_at_marker:
            self._stop_clocks()
            self._announce()
            self.pausedAtMarker.emit()
        elif result.finished:
            self._stop_clocks()
            self._finish_rehearsal()
            self._announce()
            self.finished.emit()
        elif result.state_changed:
            self._announce()

        if result.needs_repaint:
            self.repaintRequested.emit()

    def _stop_clocks(self) -> None:
        self._timer.stop()
        self._readout.stop()
        self._emit_readouts()

    def _announce(self) -> None:
        self.stateChanged.emit(self.transport.state)
        self.countdownChanged.emit(self.transport.countdown_value)

    def _emit_readouts(self) -> None:
        settings = self._state.settings
        total = self.transport.metrics.total_px

        self.progressChanged.emit(self.transport.progress)
        self.remainingChanged.emit(
            timing.remaining_seconds(self.transport.scroll_y, total, settings.speed)
        )
        self.elapsedChanged.emit(self.transport.elapsed_seconds)
        self.wpmChanged.emit(self.current_wpm())
        self.paceChanged.emit(
            timing.pace_of(
                self.transport.progress,
                self.transport.elapsed_seconds,
                float(settings.target_duration),
            )
        )

    # ── Rehearsal recording ───────────────────────────────────────────────────
    def _begin_rehearsal(self) -> None:
        self._chapter_marks.clear()
        self._chapter_started_at = 0.0
        self._current_chapter = ""

    def note_chapter(self, title: str) -> None:
        """Called by the prompter when the focus line enters a new chapter."""
        if title == self._current_chapter:
            return
        if self._current_chapter:
            self._chapter_marks.append(
                (self._current_chapter, self.transport.elapsed_seconds - self._chapter_started_at)
            )
        self._current_chapter = title
        self._chapter_started_at = self.transport.elapsed_seconds

    def _finish_rehearsal(self) -> None:
        if self._current_chapter:
            self._chapter_marks.append(
                (self._current_chapter, self.transport.elapsed_seconds - self._chapter_started_at)
            )
        if self.transport.elapsed_seconds < 1.0:
            return
        self._state.add_rehearsal(
            RehearsalRun(
                finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                duration_seconds=self.transport.elapsed_seconds,
                word_count=self._word_count,
                chapter_seconds=tuple(self._chapter_marks),
            )
        )

    # ── Reactions ─────────────────────────────────────────────────────────────
    def _on_script_changed(self, script: Script) -> None:
        self._word_count = script.word_count
        self._emit_readouts()

    def shutdown(self) -> None:
        self._timer.stop()
        self._readout.stop()


__all__ = ["AppState", "PlayState", "PlaybackController"]
