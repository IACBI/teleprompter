"""Voice-activated scrolling.

The microphone is only used to answer one question sixty times a second: is the
presenter speaking right now? A short-term RMS level is computed in PortAudio's
callback and read by a Qt timer on the GUI thread — audio is never buffered,
written to disk, or sent anywhere.

The PortAudio callback runs on a realtime audio thread, so it does the minimum
possible work: one float write. Signal emission happens on the GUI thread.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger(__name__)

try:
    import numpy as _np
    import sounddevice as _sd

    AUDIO_AVAILABLE = True
except Exception:
    _np = None  # type: ignore[assignment]
    _sd = None  # type: ignore[assignment]
    AUDIO_AVAILABLE = False

SAMPLE_RATE = 16_000
BLOCK_SIZE = 512
POLL_INTERVAL_MS = 50

#: How quickly the gate opens and closes, as a per-poll blend factor. Opening
#: fast avoids clipping the first word; closing slowly avoids stuttering during
#: the natural gaps inside a sentence.
ATTACK = 0.55
RELEASE = 0.08


class AudioMonitor(QObject):
    """Reports whether the presenter is currently speaking."""

    #: Smoothed 0.0–1.0 gate: 1.0 means "speaking, scroll at full speed".
    gateChanged = Signal(float)
    #: Raw input level, for the sensitivity meter in the UI.
    levelChanged = Signal(float)
    #: Emitted with a user-facing message when capture cannot start or dies.
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stream = None
        self._threshold = 0.025
        self._level = 0.0  # written by the audio thread, read by the poll timer
        self._gate = 0.0

        self._poll = QTimer(self)
        self._poll.setInterval(POLL_INTERVAL_MS)
        self._poll.timeout.connect(self._emit_state)

    @property
    def available(self) -> bool:
        return AUDIO_AVAILABLE

    @property
    def running(self) -> bool:
        return self._stream is not None

    @property
    def gate(self) -> float:
        return self._gate

    def set_threshold(self, threshold: float) -> None:
        self._threshold = max(0.0, threshold)

    def start(self) -> bool:
        """Open the input stream. Returns True if capture is running."""
        if self._stream is not None:
            return True
        if not AUDIO_AVAILABLE:
            self.failed.emit(
                "Voice detection needs extra packages.\n\n"
                "Install them with:  pip install sounddevice numpy"
            )
            return False

        try:
            self._stream = _sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                blocksize=BLOCK_SIZE,
                callback=self._on_audio,
            )
            self._stream.start()
        except Exception as exc:
            log.warning("Microphone capture could not start: %s", exc)
            self._stream = None
            self.failed.emit(f"The microphone could not be opened.\n\n{exc}")
            return False

        self._poll.start()
        return True

    def stop(self) -> None:
        """Close the stream and release the device."""
        self._poll.stop()
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                log.debug("Microphone stream did not close cleanly", exc_info=True)
        self._level = 0.0
        self._gate = 0.0
        self.gateChanged.emit(0.0)
        self.levelChanged.emit(0.0)

    # ── Audio thread ──────────────────────────────────────────────────────────
    def _on_audio(self, indata, _frames, _time, _status) -> None:
        """Runs on PortAudio's realtime thread — keep this tiny and allocation-free."""
        self._level = float(_np.sqrt(_np.mean(_np.square(indata))))

    # ── GUI thread ────────────────────────────────────────────────────────────
    def _emit_state(self) -> None:
        level = self._level
        target = 1.0 if level > self._threshold else 0.0
        blend = ATTACK if target > self._gate else RELEASE
        self._gate += blend * (target - self._gate)
        if self._gate < 1e-3:
            self._gate = 0.0

        self.levelChanged.emit(level)
        self.gateChanged.emit(self._gate)
