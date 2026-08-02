"""The progress scrubber.

Doubles as chapter navigation: every ``[CHAPTER]`` marker becomes a tick, so the
shape of the script is visible at a glance and any point in it is one click away.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ...theme.tokens import Palette

TRACK_HEIGHT = 6
HOVER_HEIGHT = 10


class SeekBar(QWidget):
    """A click-to-seek progress bar with chapter ticks."""

    seeked = Signal(float)  # 0.0 – 1.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette: Palette | None = None
        self._progress = 0.0
        self._hover = False
        self._hover_fraction = 0.0
        self._marks: tuple[float, ...] = ()

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(HOVER_HEIGHT + 8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Script progress")
        self.setToolTip("Click anywhere to jump to that point in the script")

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def set_progress(self, value: float) -> None:
        value = max(0.0, min(1.0, value))
        if abs(value - self._progress) < 0.0005:
            return
        self._progress = value
        self.setAccessibleDescription(f"{int(value * 100)} per cent through the script")
        self.update()

    def set_chapter_marks(self, fractions: tuple[float, ...]) -> None:
        self._marks = fractions
        self.update()

    # ── Interaction ───────────────────────────────────────────────────────────
    def _fraction_at(self, x: float) -> float:
        return max(0.0, min(1.0, x / max(1, self.width())))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.seeked.emit(self._fraction_at(event.position().x()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self._hover_fraction = self._fraction_at(event.position().x())
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.seeked.emit(self._hover_fraction)
        self.update()
        super().mouseMoveEvent(event)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        step = 0.05 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0.01
        if event.key() == Qt.Key.Key_Left:
            self.seeked.emit(max(0.0, self._progress - step))
        elif event.key() == Qt.Key.Key_Right:
            self.seeked.emit(min(1.0, self._progress + step))
        elif event.key() == Qt.Key.Key_Home:
            self.seeked.emit(0.0)
        elif event.key() == Qt.Key.Key_End:
            self.seeked.emit(1.0)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    # ── Painting ──────────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:
        palette = self._palette
        if palette is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        height = HOVER_HEIGHT if (self._hover or self.hasFocus()) else TRACK_HEIGHT
        top = (self.height() - height) / 2
        radius = height / 2
        width = self.width()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(palette.border))
        painter.drawRoundedRect(QRectF(0, top, width, height), radius, radius)

        if self._progress > 0:
            painter.setBrush(QColor(palette.accent))
            painter.drawRoundedRect(
                QRectF(0, top, max(height, width * self._progress), height), radius, radius
            )

        tick = QColor(palette.text_subtle)
        tick.setAlpha(150)
        painter.setBrush(tick)
        for fraction in self._marks:
            x = width * fraction
            painter.drawRoundedRect(QRectF(x - 1, top, 2, height), 1, 1)

        if self._hover:
            marker = QColor(palette.text)
            marker.setAlpha(120)
            painter.setBrush(marker)
            painter.drawRoundedRect(
                QRectF(width * self._hover_fraction - 1, top - 2, 2, height + 4), 1, 1
            )
