"""Playback state machine and scroll motion.

Kept free of Qt so the whole transport — countdown, easing, pause markers,
end-of-script detection — can be driven by a fake clock in tests.

The controller feeds this class real elapsed milliseconds; it never assumes a
fixed frame rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from .timing import FRAME_MS, ramp

#: Elapsed time is clamped into this window so a stalled frame (garbage
#: collection, window drag, laptop resuming from sleep) cannot teleport the
#: script forward.
MIN_DT_MS = 1.0
MAX_DT_MS = 100.0


class PlayState(Enum):
    IDLE = "idle"
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"

    @property
    def is_active(self) -> bool:
        """True while the transport wants clock ticks."""
        return self in (PlayState.COUNTDOWN, PlayState.PLAYING)


@dataclass(frozen=True)
class TickResult:
    """What changed during one :meth:`Transport.tick`."""

    state_changed: bool = False
    moved: bool = False
    finished: bool = False
    countdown_changed: bool = False
    focus_line_changed: bool = False
    paused_at_marker: bool = False

    @property
    def needs_repaint(self) -> bool:
        return self.moved or self.state_changed or self.countdown_changed or self.focus_line_changed


@dataclass
class Metrics:
    """Layout facts the transport needs in order to move correctly."""

    total_px: float = 0.0
    line_height: int = 1
    pause_lines: frozenset[int] = frozenset()


@dataclass
class Transport:
    """Scroll position, playback state and easing."""

    state: PlayState = PlayState.IDLE
    scroll_y: float = 0.0
    velocity: float = 0.0
    elapsed_seconds: float = 0.0
    countdown_remaining: float = 0.0
    metrics: Metrics = field(default_factory=Metrics)
    _focus_line: int = -1
    _last_countdown_shown: int | None = None

    # ── Queries ───────────────────────────────────────────────────────────────
    @property
    def is_playing(self) -> bool:
        return self.state is PlayState.PLAYING

    @property
    def countdown_value(self) -> int | None:
        """Whole seconds to show during the countdown, or None."""
        if self.state is not PlayState.COUNTDOWN:
            return None
        return max(1, math.ceil(self.countdown_remaining - 1e-6))

    @property
    def focus_line(self) -> int:
        return self._focus_line

    @property
    def progress(self) -> float:
        """Completion as 0.0–1.0."""
        total = self.metrics.total_px
        if total <= 0:
            return 0.0
        return min(1.0, max(0.0, self.scroll_y / total))

    @property
    def at_end(self) -> bool:
        return self.metrics.total_px > 0 and self.scroll_y >= self.metrics.total_px

    # ── Configuration ─────────────────────────────────────────────────────────
    def set_metrics(self, total_px: float, line_height: int, pause_lines: frozenset[int]) -> None:
        """Update layout facts, preserving the reader's place proportionally."""
        old = self.metrics
        self.metrics = Metrics(
            total_px=max(0.0, total_px),
            line_height=max(1, line_height),
            pause_lines=pause_lines,
        )
        # A font or width change re-flows the script; keep the same relative
        # position so the presenter doesn't lose their place mid-read.
        if old.total_px > 0 and total_px > 0 and self.scroll_y > 0:
            self.scroll_y = min(total_px, self.scroll_y * (total_px / old.total_px))
        self._focus_line = self._line_at(self.scroll_y)

    # ── Commands ──────────────────────────────────────────────────────────────
    def start(self, countdown_secs: int = 0) -> bool:
        """Begin playback, optionally after a countdown. Returns True if changed."""
        if self.state is PlayState.PLAYING:
            return False
        if self.at_end:
            self.scroll_y = 0.0
            self.elapsed_seconds = 0.0
        if countdown_secs > 0:
            self.state = PlayState.COUNTDOWN
            self.countdown_remaining = float(countdown_secs)
            self._last_countdown_shown = None
        else:
            self.state = PlayState.PLAYING
        return True

    def pause(self) -> bool:
        if self.state not in (PlayState.PLAYING, PlayState.COUNTDOWN):
            return False
        self.state = PlayState.PAUSED
        self.countdown_remaining = 0.0
        self.velocity = 0.0
        return True

    def toggle(self, countdown_secs: int = 0) -> bool:
        if self.state.is_active:
            return self.pause()
        return self.start(countdown_secs)

    def reset(self) -> bool:
        changed = (
            self.scroll_y != 0.0 or self.state is not PlayState.IDLE or self.elapsed_seconds != 0.0
        )
        self.state = PlayState.IDLE
        self.scroll_y = 0.0
        self.velocity = 0.0
        self.elapsed_seconds = 0.0
        self.countdown_remaining = 0.0
        self._focus_line = 0
        self._last_countdown_shown = None
        return changed

    def seek_pixels(self, delta: float) -> bool:
        """Nudge the script by ``delta`` pixels, clamped to the script bounds."""
        return self.seek_to(self.scroll_y + delta)

    def seek_to(self, position: float) -> bool:
        target = min(max(0.0, position), self.metrics.total_px)
        if target == self.scroll_y:
            return False
        self.scroll_y = target
        self._focus_line = self._line_at(target)
        if self.state is PlayState.FINISHED and target < self.metrics.total_px:
            self.state = PlayState.PAUSED
        return True

    def seek_to_line(self, line_index: int) -> bool:
        return self.seek_to(line_index * self.metrics.line_height)

    # ── Clock ─────────────────────────────────────────────────────────────────
    def tick(
        self, dt_ms: float, target_speed: float, *, ramp_tau: float = 0.0, gate: float = 1.0
    ) -> TickResult:
        """Advance the transport by ``dt_ms`` milliseconds.

        ``target_speed`` is the configured scroll speed; ``gate`` scales it
        (voice-activated scrolling passes 0.0 during silence). ``ramp_tau`` of
        zero disables easing and applies the speed instantly.
        """
        dt_ms = min(MAX_DT_MS, max(MIN_DT_MS, dt_ms))
        dt_s = dt_ms / 1000.0

        if self.state is PlayState.COUNTDOWN:
            return self._tick_countdown(dt_s)

        if self.state is not PlayState.PLAYING:
            return TickResult()

        self.elapsed_seconds += dt_s

        desired = max(0.0, target_speed) * max(0.0, min(1.0, gate))
        self.velocity = ramp(self.velocity, desired, dt_s, ramp_tau)

        before = self.scroll_y
        self.scroll_y += (self.velocity / FRAME_MS) * dt_ms
        moved = self.scroll_y != before

        focus_changed = False
        paused_at_marker = False
        state_changed = False

        line = self._line_at(self.scroll_y)
        if line != self._focus_line:
            self._focus_line = line
            focus_changed = True
            if line in self.metrics.pause_lines:
                # Land exactly on the marker so resuming reads from its top.
                self.scroll_y = float(line * self.metrics.line_height)
                self.state = PlayState.PAUSED
                self.velocity = 0.0
                paused_at_marker = True
                state_changed = True

        finished = False
        if not paused_at_marker and self.at_end:
            self.scroll_y = self.metrics.total_px
            self.state = PlayState.FINISHED
            self.velocity = 0.0
            finished = True
            state_changed = True

        return TickResult(
            state_changed=state_changed,
            moved=moved,
            finished=finished,
            focus_line_changed=focus_changed,
            paused_at_marker=paused_at_marker,
        )

    # ── Internals ─────────────────────────────────────────────────────────────
    def _tick_countdown(self, dt_s: float) -> TickResult:
        self.countdown_remaining -= dt_s
        shown = self.countdown_value
        changed = shown != self._last_countdown_shown
        self._last_countdown_shown = shown

        if self.countdown_remaining <= 0.0:
            self.state = PlayState.PLAYING
            self.countdown_remaining = 0.0
            self._last_countdown_shown = None
            return TickResult(state_changed=True, countdown_changed=True)

        return TickResult(countdown_changed=changed)

    def _line_at(self, position: float) -> int:
        return int(position // self.metrics.line_height)
