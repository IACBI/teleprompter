"""Vector icons, drawn at runtime.

Emoji were previously used as button labels. They render differently on every
platform, cannot be recoloured, and a screen reader announces "wastebasket"
rather than "Delete". These are stroked SVG paths on a 24×24 grid instead —
crisp at any scale factor, tinted to match the active palette, and always paired
with a real accessible name at the call site.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtSvg import QSvgRenderer

GRID = 24.0

#: name → (path data, fill?) on a 24×24 grid.
_PATHS: dict[str, tuple[str, bool]] = {
    # Transport
    "play": ("M8 5.2 L19 12 L8 18.8 Z", True),
    "pause": ("M8.5 5.5 h2.6 v13 h-2.6 Z M12.9 5.5 h2.6 v13 h-2.6 Z", True),
    "stop": ("M6.5 6.5 h11 v11 h-11 Z", True),
    "rewind": ("M6 5.5 v13 M19 5.8 L9.5 12 L19 18.2 Z", True),
    "skip-back": ("M5.5 6 v12 M18.5 6.4 L10 12 L18.5 17.6 Z", True),
    "skip-forward": ("M18.5 6 v12 M5.5 6.4 L14 12 L5.5 17.6 Z", True),
    "plus": ("M12 5.5 V18.5 M5.5 12 H18.5", False),
    "minus": ("M5.5 12 H18.5", False),
    # Navigation
    "script": (
        "M6 3.5 h8.5 L18 7 v13.5 h-12 Z M14 3.5 v3.5 h3.5 M9 12 h6 M9 15.5 h6 M9 8.5 h2.5",
        False,
    ),
    "playback": (
        "M12 3.5 a8.5 8.5 0 1 0 0 17 a8.5 8.5 0 0 0 0 -17 M10 8.5 L16 12 L10 15.5 Z",
        False,
    ),
    "display": ("M3.5 5 h17 v11 h-17 Z M9 20 h6 M12 16 v4", False),
    "mic": (
        "M12 3.5 a2.8 2.8 0 0 1 2.8 2.8 v5 a2.8 2.8 0 0 1 -5.6 0 v-5 A2.8 2.8 0 0 1 12 3.5 Z"
        " M6.5 11 a5.5 5.5 0 0 0 11 0 M12 16.5 v4 M9 20.5 h6",
        False,
    ),
    "timing": ("M12 4 a8 8 0 1 0 0 16 a8 8 0 0 0 0 -16 M12 7.5 v5 l3.5 2.2 M9.5 2.5 h5", False),
    "settings": (
        "M4 7.5 h5 M13 7.5 h7 M4 16.5 h7 M15 16.5 h5"
        " M11 7.5 a2 2 0 1 0 0.01 0 M13 16.5 a2 2 0 1 0 0.01 0",
        False,
    ),
    # Actions
    "save": ("M5 4.5 h11.5 L19 7 v12.5 h-14 Z M8 4.5 v5 h7 v-5 M8 19.5 v-6 h8 v6", False),
    "folder": ("M3.5 6 h6 l2 2.5 h9 v11 h-17 Z", False),
    "trash": (
        "M4.5 6.5 h15 M9.5 6.5 v-2.5 h5 v2.5 M6.5 6.5 v13 h11 v-13 M10 10 v6 M14 10 v6",
        False,
    ),
    "undo": ("M9 8 L4.5 12 L9 16 M4.5 12 h9.5 a5.5 5.5 0 0 1 0 11 h-3", False),
    "redo": ("M15 8 L19.5 12 L15 16 M19.5 12 h-9.5 a5.5 5.5 0 0 0 0 11 h3", False),
    "download": ("M12 3.5 v11 M8 10.5 L12 14.5 L16 10.5 M4.5 17 v3.5 h15 V17", False),
    "upload": ("M12 14.5 v-11 M8 7.5 L12 3.5 L16 7.5 M4.5 17 v3.5 h15 V17", False),
    "fullscreen": ("M4 9.5 V4.5 h5 M15 4.5 h5 v5 M20 14.5 v5 h-5 M9 19.5 H4 v-5", False),
    "notes": ("M5 4.5 h14 v10 l-5 5 h-9 Z M19 14.5 h-5 v5 M8.5 9 h7 M8.5 12.5 h4", False),
    "chapter": ("M7 3.5 h10 v17 L12 16 L7 20.5 Z", False),
    "chevron-left": ("M15 5.5 L8 12 L15 18.5", False),
    "chevron-right": ("M9 5.5 L16 12 L9 18.5", False),
    "chevron-down": ("M5.5 9 L12 16 L18.5 9", False),
    "close": ("M6 6 L18 18 M18 6 L6 18", False),
    "check": ("M5 12.5 L10 17.5 L19 6.5", False),
    "info": ("M12 3.5 a8.5 8.5 0 1 0 0 17 a8.5 8.5 0 0 0 0 -17 M12 11 v6 M12 7.4 v0.2", False),
    "warning": ("M12 4 L21 19.5 H3 Z M12 9.5 v5 M12 17.2 v0.2", False),
    "error": (
        "M12 3.5 a8.5 8.5 0 1 0 0 17 a8.5 8.5 0 0 0 0 -17 M8.5 8.5 L15.5 15.5 M15.5 8.5 L8.5 15.5",
        False,
    ),
    "success": ("M12 3.5 a8.5 8.5 0 1 0 0 17 a8.5 8.5 0 0 0 0 -17 M8 12.2 L11 15.2 L16 9.2", False),
    "mirror": ("M12 3 v18 M8.5 7.5 L4 12 l4.5 4.5 Z M15.5 7.5 L20 12 l-4.5 4.5 Z", False),
    "monitor-multi": ("M2.5 5 h13 v9 h-13 Z M18 8 h3.5 v9 h-11 v-3 M6.5 18 h5 M9 14 v4", False),
    "search": ("M10.5 4 a6.5 6.5 0 1 0 0 13 a6.5 6.5 0 0 0 0 -13 M15.2 15.2 L20.5 20.5", False),
}

_SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'width="{size}" height="{size}">'
    '<path d="{path}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def svg_markup(name: str, color: str, size: int = 24, stroke_width: float = 1.7) -> str:
    """Return standalone SVG markup for one icon."""
    path, filled = _PATHS.get(name, _PATHS["info"])
    return _SVG_TEMPLATE.format(
        size=size,
        path=path,
        fill=color if filled else "none",
        stroke=color if not filled else "none",
        width=stroke_width,
    )


@lru_cache(maxsize=512)
def _render(name: str, color: str, size: int, stroke_width: float, ratio_x100: int) -> QPixmap:
    ratio = ratio_x100 / 100.0
    renderer = QSvgRenderer(QByteArray(svg_markup(name, color, size, stroke_width).encode()))
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def icon_pixmap(
    name: str, color: str, size: int = 18, *, stroke_width: float = 1.7, ratio: float = 2.0
) -> QPixmap:
    """A tinted pixmap, rendered above device resolution so it stays crisp."""
    return _render(name, color, size, stroke_width, int(ratio * 100))


def icon(name: str, color: str, size: int = 18, *, stroke_width: float = 1.7) -> QIcon:
    """A :class:`QIcon` for ``name`` tinted with ``color``."""
    result = QIcon()
    for ratio in (1.0, 2.0, 3.0):
        result.addPixmap(icon_pixmap(name, color, size, stroke_width=stroke_width, ratio=ratio))
    return result


def available_icons() -> tuple[str, ...]:
    return tuple(sorted(_PATHS))


# ══════════════════════════════════════════════════════════════════════════════
#  Application icon
# ══════════════════════════════════════════════════════════════════════════════
def _draw_app_mark(painter: QPainter, size: int, accent: QColor) -> None:
    """Three scrolling lines with an amber focus band — the prompter metaphor."""
    unit = size / 256.0

    def u(value: float) -> float:
        return value * unit

    backdrop = QLinearGradient(0, 0, 0, size)
    backdrop.setColorAt(0.0, QColor("#1d2029"))
    backdrop.setColorAt(1.0, QColor("#0b0c11"))
    painter.setBrush(QBrush(backdrop))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(u(6), u(6), u(244), u(244)), u(56), u(56))

    painter.setPen(QPen(QColor(255, 255, 255, 26), u(3)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(u(7.5), u(7.5), u(241), u(241)), u(55), u(55))

    left, width, height = u(44), u(168), u(20)
    rows = (u(78), u(124), u(170))

    band = QLinearGradient(0, rows[1] - u(14), 0, rows[1] + height + u(14))
    band.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
    band.setColorAt(0.5, QColor(accent.red(), accent.green(), accent.blue(), 48))
    band.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
    painter.setBrush(QBrush(band))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRect(QRectF(u(20), rows[1] - u(14), u(216), height + u(28)))

    for index, y in enumerate(rows):
        if index == 1:
            sweep = QLinearGradient(left, y, left + width, y)
            sweep.setColorAt(0.0, accent.lighter(115))
            sweep.setColorAt(1.0, accent)
            painter.setBrush(QBrush(sweep))
            row_width = width
        else:
            painter.setBrush(QColor(220, 226, 240, 96 if index == 0 else 62))
            row_width = width * (0.74 if index == 0 else 0.52)
        painter.drawRoundedRect(QRectF(left, y, row_width, height), u(7), u(7))

    painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 120), u(2.5)))
    for offset in (-u(13), height + u(13)):
        painter.drawLine(
            QPoint(int(u(28)), int(rows[1] + offset)),
            QPoint(int(u(228)), int(rows[1] + offset)),
        )

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#3dd68c"))
    tip, top, span = u(196), u(196), u(34)
    painter.drawPolygon(
        QPolygon(
            [
                QPoint(int(tip), int(top + span)),
                QPoint(int(tip), int(top)),
                QPoint(int(tip + span), int(top + span / 2)),
            ]
        )
    )


def app_icon(accent: str = "#ffb020") -> QIcon:
    """The window and taskbar icon, drawn at several sizes."""
    result = QIcon()
    colour = QColor(accent)
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _draw_app_mark(painter, size, colour)
        painter.end()
        result.addPixmap(pixmap)
    return result


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    """Shared helper for the overlay's rounded chrome."""
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def icon_size(size: int) -> QSize:
    return QSize(size, size)
