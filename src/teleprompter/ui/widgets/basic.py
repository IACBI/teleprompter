"""Layout primitives and the icon button."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...resources import icons
from ...theme.stylesheet import repolish
from ...theme.tokens import MIN_HIT_TARGET, SPACE, Palette


def set_variant(widget: QWidget, variant: str) -> None:
    """Set the ``variant`` style property and repolish so it takes effect."""
    widget.setProperty("variant", variant)
    repolish(widget)


def label(
    text: str, role: str = "", *, wrap: bool = False, align: Qt.AlignmentFlag | None = None
) -> QLabel:
    """A QLabel that renders user content literally.

    ``QLabel`` auto-detects rich text, so a script note containing markup would
    otherwise be interpreted as HTML. Everything here is plain text unless a
    caller deliberately says otherwise.
    """
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if role:
        widget.setProperty("role", role)
    if wrap:
        widget.setWordWrap(True)
    if align is not None:
        widget.setAlignment(align)
    return widget


class Separator(QWidget):
    """A one-pixel rule."""

    def __init__(self, horizontal: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Separator")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if horizontal:
            self.setFixedHeight(1)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.setFixedWidth(1)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)


class Card(QWidget):
    """A titled container. Pages are built from these instead of group boxes."""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        # A QWidget subclass ignores its stylesheet background unless it is told
        # to paint one — without this the cards are invisible.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACE.lg, SPACE.lg, SPACE.lg, SPACE.lg)
        outer.setSpacing(SPACE.md)

        if title:
            header = QVBoxLayout()
            header.setSpacing(SPACE.xxs)
            header.addWidget(label(title, "title"))
            if subtitle:
                header.addWidget(label(subtitle, "caption", wrap=True))
            outer.addLayout(header)

        self.body = QVBoxLayout()
        self.body.setSpacing(SPACE.md)
        outer.addLayout(self.body)

    def add(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        self.body.addLayout(layout)

    def add_row(
        self, text: str, widget: QWidget, hint: str = "", *, expand: bool = True
    ) -> QWidget:
        """Add a labelled row. Set ``expand=False`` for badges and chips that
        should hug their content instead of filling the column."""
        self.body.addWidget(FieldRow(text, widget, hint, expand=expand))
        return widget


class FieldRow(QWidget):
    """A labelled control: caption on the left, control on the right."""

    LABEL_WIDTH = 116

    def __init__(
        self,
        text: str,
        control: QWidget,
        hint: str = "",
        parent: QWidget | None = None,
        *,
        expand: bool = True,
    ) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SPACE.xxs)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACE.md)

        caption = label(text, "muted")
        caption.setFixedWidth(self.LABEL_WIDTH)
        caption.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        caption.setBuddy(control)
        row.addWidget(caption)
        if expand:
            row.addWidget(control, 1)
        else:
            row.addWidget(control, 0)
            row.addStretch(1)
        column.addLayout(row)

        if hint:
            note = label(hint, "caption", wrap=True)
            note.setContentsMargins(self.LABEL_WIDTH + SPACE.md, 0, 0, 0)
            column.addWidget(note)

        if not control.accessibleName():
            control.setAccessibleName(text.rstrip(":"))


class IconButton(QPushButton):
    """A button whose face is a vector icon but whose name is real text."""

    def __init__(
        self,
        icon_name: str,
        tooltip: str,
        *,
        size: int = MIN_HIT_TARGET,
        icon_size: int = 18,
        variant: str = "ghost",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self._icon_size = icon_size
        # Tells the application sheet to stop imposing padding and a minimum
        # height, so the square geometry below is what actually renders.
        self.setProperty("shape", "fixed")
        self.setFixedSize(QSize(size, size))
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        set_variant(self, variant)

    def apply_palette(self, palette: Palette, color: str | None = None) -> None:
        """Retint the icon when the theme changes."""
        tint = color or (
            palette.text_muted if self.property("variant") == "ghost" else palette.text
        )
        self.setIcon(icons.icon(self._icon_name, tint, self._icon_size))
        self.setIconSize(QSize(self._icon_size, self._icon_size))

    def set_icon_name(self, name: str, palette: Palette, color: str | None = None) -> None:
        self._icon_name = name
        self.apply_palette(palette, color)


def apply_shadow(
    widget: QWidget, palette: Palette, *, blur: int = 28, y_offset: int = 6, alpha: int = 90
) -> None:
    """Attach a soft drop shadow. Qt stylesheets cannot express one."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    colour = QColor(0, 0, 0) if palette.is_dark else QColor(60, 66, 76)
    colour.setAlpha(alpha)
    effect.setColor(colour)
    widget.setGraphicsEffect(effect)
