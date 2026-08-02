"""Status and notification widgets.

Modal dialogs interrupt. Almost everything the app has to say — a file loaded, a
save failed, the microphone disappeared — belongs in a toast that appears,
states the fact, and leaves. Only questions that genuinely block progress stay
modal.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ...core.timing import Pace, ReadingBand
from ...resources import icons
from ...theme.tokens import MOTION, RADIUS, SPACE, TYPE, Palette
from .basic import label

#: severity → (icon name, palette attribute holding the accent colour)
_SEVERITY: dict[str, tuple[str, str]] = {
    "info": ("info", "info"),
    "success": ("success", "success"),
    "warning": ("warning", "warning"),
    "error": ("error", "danger"),
}


class Toast(QWidget):
    """A single transient message."""

    def __init__(
        self, text: str, severity: str, palette: Palette, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        # QWidget subclasses need this before they will paint a stylesheet
        # background at all.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        icon_name, colour_attr = _SEVERITY.get(severity, _SEVERITY["info"])
        accent = getattr(palette, colour_attr)

        self.setStyleSheet(
            f"background: {palette.surface_overlay};"
            f" border: 1px solid {palette.border_strong};"
            f" border-left: 3px solid {accent};"
            f" border-radius: {RADIUS.md}px;"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(SPACE.md, SPACE.md, SPACE.md, SPACE.md)
        row.setSpacing(SPACE.md)

        glyph = QLabel()
        glyph.setPixmap(icons.icon_pixmap(icon_name, accent, 18))
        glyph.setFixedSize(18, 18)
        glyph.setStyleSheet("border: none;")
        row.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)

        message = label(text, wrap=True)
        message.setStyleSheet(f"border: none; color: {palette.text}; font-size: {TYPE.body}px;")
        message.setMaximumWidth(340)
        row.addWidget(message, 1)

        self.setAccessibleName(f"{severity} notification")
        self.setAccessibleDescription(text)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._animation: QPropertyAnimation | None = None

    def fade(self, to: float, duration: int, on_done=None) -> None:
        animation = QPropertyAnimation(self._opacity, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(self._opacity.opacity())
        animation.setEndValue(to)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        if on_done is not None:
            animation.finished.connect(on_done)
        animation.start()
        self._animation = animation  # keep a reference so it is not collected


class ToastHost(QWidget):
    """Stacks toasts in the bottom-right corner of its parent."""

    MARGIN = SPACE.lg
    MAX_VISIBLE = 4

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._palette: Palette | None = None
        self._toasts: list[Toast] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE.sm)
        self._layout.addStretch(1)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette

    def show_message(self, text: str, severity: str = "info", duration: int = MOTION.toast) -> None:
        if self._palette is None or not text:
            return

        while len(self._toasts) >= self.MAX_VISIBLE:
            self._remove(self._toasts[0])

        toast = Toast(text, severity, self._palette, self)
        self._layout.addWidget(toast, 0, Qt.AlignmentFlag.AlignRight)
        self._toasts.append(toast)
        toast.show()
        toast.fade(1.0, MOTION.base)

        QTimer.singleShot(duration, lambda: self._dismiss(toast))
        self._reposition()

    def _dismiss(self, toast: Toast) -> None:
        if toast not in self._toasts:
            return
        toast.fade(0.0, MOTION.base, on_done=lambda: self._remove(toast))

    def _remove(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._layout.removeWidget(toast)
        toast.deleteLater()
        self._reposition()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        width = min(400, parent.width() - 2 * self.MARGIN)
        self.setFixedWidth(max(200, width))
        self.adjustSize()
        self.move(
            QPoint(
                parent.width() - self.width() - self.MARGIN,
                parent.height() - self.height() - self.MARGIN,
            )
        )
        self.raise_()

    def parent_resized(self) -> None:
        self._reposition()


class StatChip(QWidget):
    """A compact label/value readout for the transport bar."""

    def __init__(self, caption: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self._caption = label(caption.upper(), "section")
        self._value = label(value, "title")
        self._value.setTextFormat(Qt.TextFormat.PlainText)
        column.addWidget(self._caption)
        column.addWidget(self._value)

        self.setAccessibleName(caption)

    def set_value(self, text: str, colour: str | None = None) -> None:
        self._value.setText(text)
        self.setAccessibleDescription(f"{self._caption.text()}: {text}")
        self._value.setStyleSheet(f"color: {colour};" if colour else "")


#: Pace → (label, icon, palette attribute). Colour is never the only cue.
_PACE_LOOK: dict[Pace, tuple[str, str, str]] = {
    Pace.AHEAD: ("Ahead of time", "chevron-down", "info"),
    Pace.ON_TRACK: ("On track", "check", "success"),
    Pace.BEHIND: ("Running late", "warning", "warning"),
    # The badge is only shown once a target exists, so "unknown" means the run
    # has not started rather than that nothing was set.
    Pace.UNKNOWN: ("Ready to start", "info", "text_subtle"),
}

#: Reading band → plain-language description shown next to the WPM figure.
BAND_TEXT: dict[ReadingBand, str] = {
    ReadingBand.SLOW: "Deliberate",
    ReadingBand.COMFORTABLE: "Comfortable",
    ReadingBand.FAST: "Brisk",
    ReadingBand.TOO_FAST: "Hard to follow",
}


class PaceBadge(QWidget):
    """Shows whether the run is on schedule, with an icon and words as well as colour."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._palette: Palette | None = None
        self._pace = Pace.UNKNOWN

        row = QHBoxLayout(self)
        row.setContentsMargins(SPACE.sm, SPACE.xs, SPACE.md, SPACE.xs)
        row.setSpacing(SPACE.sm)

        self._glyph = QLabel()
        self._glyph.setFixedSize(16, 16)
        self._text = label("No target set", "value")
        row.addWidget(self._glyph)
        row.addWidget(self._text)

        self.setAccessibleName("Pace")

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.set_pace(self._pace)

    def set_pace(self, pace: Pace) -> None:
        self._pace = pace
        if self._palette is None:
            return
        text, icon_name, colour_attr = _PACE_LOOK[pace]
        colour = getattr(self._palette, colour_attr)
        self._glyph.setPixmap(icons.icon_pixmap(icon_name, colour, 16))
        self._text.setText(text)
        self._text.setStyleSheet(f"color: {colour};")
        self.setAccessibleDescription(text)
        self.setStyleSheet(
            f"background: {self._palette.surface_raised};"
            f" border: 1px solid {self._palette.border};"
            f" border-radius: {RADIUS.pill}px;"
        )
