"""Input controls.

These replace the stock combo boxes and check boxes on the settings pages. A
segmented control shows every option at once, which is what you want when a
choice has to be made quickly under studio lights, and a switch reads as a state
rather than a form field.

Everything here is keyboard reachable and animates with the shared motion tokens.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QColorDialog,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QWidget,
)

from ...core.settings import Range
from ...theme.tokens import MIN_HIT_TARGET, MOTION, RADIUS, SPACE, TYPE, Palette
from .basic import label


class ToggleSwitch(QAbstractButton):
    """An animated on/off switch."""

    TRACK_WIDTH = 42
    TRACK_HEIGHT = 24

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(QSize(self.TRACK_WIDTH, self.TRACK_HEIGHT))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._position = 0.0
        self._palette: Palette | None = None
        self._animation = QPropertyAnimation(self, b"position", self)
        self._animation.setDuration(MOTION.fast)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def _animate(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def get_position(self) -> float:
        return self._position

    def set_position(self, value: float) -> None:
        self._position = value
        self.update()

    position = Property(float, get_position, set_position)

    def sizeHint(self) -> QSize:
        return QSize(self.TRACK_WIDTH, self.TRACK_HEIGHT)

    def paintEvent(self, _event) -> None:
        palette = self._palette
        if palette is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_off = QColor(palette.border_strong)
        track_on = QColor(palette.accent)
        track = _blend(track_off, track_on, self._position)
        if not self.isEnabled():
            track = QColor(palette.border)

        radius = self.TRACK_HEIGHT / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, self.TRACK_WIDTH, self.TRACK_HEIGHT), radius, radius)

        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            focus = QColor(palette.accent)
            focus.setAlpha(160)
            painter.setPen(focus)
            painter.drawRoundedRect(
                QRectF(0.75, 0.75, self.TRACK_WIDTH - 1.5, self.TRACK_HEIGHT - 1.5), radius, radius
            )

        knob_size = self.TRACK_HEIGHT - 6
        travel = self.TRACK_WIDTH - knob_size - 6
        knob_x = 3 + travel * self._position
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(
            QColor("#ffffff") if palette.is_dark or self.isChecked() else QColor(palette.surface)
        )
        painter.drawEllipse(QRectF(knob_x, 3, knob_size, knob_size))


def _blend(start: QColor, end: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        int(start.red() + (end.red() - start.red()) * amount),
        int(start.green() + (end.green() - start.green()) * amount),
        int(start.blue() + (end.blue() - start.blue()) * amount),
    )


class SegmentedControl(QWidget):
    """A row of mutually exclusive options with an animated selection pill.

    Real buttons underneath, so Tab and Space work and a screen reader reads the
    option names — the pill is decoration painted behind them.
    """

    currentChanged = Signal(int)

    def __init__(self, options: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette: Palette | None = None
        self._pill_x = 0.0
        self._pill_width = 0.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        for index, text in enumerate(options):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFlat(True)
            button.setMinimumHeight(MIN_HIT_TARGET - 6)
            button.setStyleSheet("background: transparent; border: none;")
            self._group.addButton(button, index)
            layout.addWidget(button, 1)
            self._buttons.append(button)

        self._group.idClicked.connect(self._on_clicked)
        self.setFixedHeight(MIN_HIT_TARGET + 2)

        self._animation = QPropertyAnimation(self, b"pillX", self)
        self._animation.setDuration(MOTION.base)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        if self._buttons:
            self._buttons[0].setChecked(True)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._restyle()

    def _restyle(self) -> None:
        palette = self._palette
        if palette is None:
            return
        for button in self._buttons:
            colour = palette.accent if button.isChecked() else palette.text_muted
            weight = TYPE.weight_semibold if button.isChecked() else TYPE.weight_medium
            button.setStyleSheet(
                f"background: transparent; border: none; color: {colour};"
                f" font-weight: {weight}; padding: 0 {SPACE.sm}px;"
            )
        self.update()

    def get_pill_x(self) -> float:
        return self._pill_x

    def set_pill_x(self, value: float) -> None:
        self._pill_x = value
        self.update()

    pillX = Property(float, get_pill_x, set_pill_x)

    def current_index(self) -> int:
        return self._group.checkedId()

    def set_current_index(self, index: int, *, animate: bool = True) -> None:
        if not (0 <= index < len(self._buttons)):
            return
        if self._group.checkedId() == index and animate:
            return
        self._buttons[index].setChecked(True)
        self._restyle()
        self._move_pill(index, animate=animate)

    def _on_clicked(self, index: int) -> None:
        self._restyle()
        self._move_pill(index)
        self.currentChanged.emit(index)

    def _move_pill(self, index: int, *, animate: bool = True) -> None:
        button = self._buttons[index]
        target = float(button.x())
        self._pill_width = float(button.width())
        if not animate or not self.isVisible():
            self.set_pill_x(target)
            return
        self._animation.stop()
        self._animation.setStartValue(self._pill_x)
        self._animation.setEndValue(target)
        self._animation.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._move_pill(max(0, self.current_index()), animate=False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._move_pill(max(0, self.current_index()), animate=False)

    def paintEvent(self, _event) -> None:
        palette = self._palette
        if palette is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QColor(palette.border))
        painter.setBrush(QColor(palette.surface_raised))
        painter.drawRoundedRect(
            QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), RADIUS.md, RADIUS.md
        )

        if self._pill_width <= 0:
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_soft(palette.accent, 0.18 if palette.is_dark else 0.14))
        painter.drawRoundedRect(
            QRectF(self._pill_x, 3, self._pill_width, self.height() - 6),
            RADIUS.sm,
            RADIUS.sm,
        )


def _soft(hex_colour: str, alpha: float) -> QColor:
    colour = QColor(hex_colour)
    colour.setAlphaF(alpha)
    return colour


class LabeledSlider(QWidget):
    """A slider bound to a :class:`Range`, with a live value chip."""

    valueChanged = Signal(float)
    #: Emitted once the user lets go — expensive work can wait for this.
    editingFinished = Signal(float)

    def __init__(
        self,
        value_range: Range,
        *,
        suffix: str = "",
        decimals: int = 1,
        formatter=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._range = value_range
        self._suffix = suffix
        self._decimals = decimals
        self._formatter = formatter

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.md)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(value_range.slider_minimum, value_range.slider_maximum)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(
            max(1, (value_range.slider_maximum - value_range.slider_minimum) // 10)
        )
        self.slider.valueChanged.connect(self._on_slider)
        self.slider.sliderReleased.connect(lambda: self.editingFinished.emit(self.value()))

        self._chip = label("", "value")
        self._chip.setMinimumWidth(58)
        self._chip.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self.slider, 1)
        layout.addWidget(self._chip)

        self.set_value(value_range.default)

    def value(self) -> float:
        return self._range.from_slider(self.slider.value())

    def set_value(self, value: float, *, notify: bool = False) -> None:
        ticks = self._range.to_slider(value)
        if not notify:
            self.slider.blockSignals(True)
        self.slider.setValue(ticks)
        if not notify:
            self.slider.blockSignals(False)
        self._update_chip()

    def setAccessibleName(self, name: str) -> None:
        super().setAccessibleName(name)
        self.slider.setAccessibleName(name)

    def _on_slider(self, _ticks: int) -> None:
        self._update_chip()
        self.valueChanged.emit(self.value())

    def _update_chip(self) -> None:
        value = self.value()
        if self._formatter is not None:
            self._chip.setText(self._formatter(value))
        elif self._decimals == 0:
            self._chip.setText(f"{round(value)}{self._suffix}")
        else:
            self._chip.setText(f"{value:.{self._decimals}f}{self._suffix}")


class ColorSwatchButton(QPushButton):
    """Opens a colour picker; shows the current colour as a filled chip."""

    colorPicked = Signal(str)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._color = "#ffffff"
        self._palette: Palette | None = None
        self.setMinimumHeight(MIN_HIT_TARGET)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(title)
        self.setProperty("variant", "swatch")
        self.clicked.connect(self._pick)

    def color(self) -> str:
        return self._color

    def set_color(self, value: str) -> None:
        self._color = value
        self.setText(value.upper())
        self.setToolTip(f"{self._title} — {value.upper()}. Click to change.")
        self.update()

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self, self._title)
        if chosen.isValid():
            self.set_color(chosen.name())
            self.colorPicked.emit(chosen.name())

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = 16
        rect = QRectF(SPACE.md + 1, (self.height() - size) / 2, size, size)
        path = QPainterPath()
        path.addRoundedRect(rect, 4, 4)

        border = QColor(self._palette.border_strong) if self._palette else QColor("#555555")
        painter.setPen(border)
        painter.setBrush(QColor(self._color))
        painter.drawPath(path)
