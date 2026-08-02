"""PDF export.

Uses the same wrapping engine as the prompter — :func:`teleprompter.core.layout.
build_layout` — instead of a second copy of the algorithm, so a fix to one is a
fix to both. Presenter notes are stripped; they are private by definition.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPageSize, QPainter, QPdfWriter

from .. import __version__
from ..core.layout import build_layout, line_origin_x
from ..core.script import BlockKind, Script

log = logging.getLogger(__name__)

RESOLUTION_DPI = 300
MARGIN_MM = 18.0
BODY_POINT_SIZE = 13.0
TITLE_POINT_SIZE = 22.0


def export_script_to_pdf(
    script: Script, destination: str | Path, *, title: str = "Script", font_family: str = "Arial"
) -> str | None:
    """Write ``script`` to a printable PDF. Returns an error message, or None."""
    path = Path(destination)
    try:
        writer = QPdfWriter(str(path))
        writer.setResolution(RESOLUTION_DPI)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(
            QMarginsF(MARGIN_MM, MARGIN_MM, MARGIN_MM, MARGIN_MM),
            QPageSize.Unit.Millimeter,
        )
        writer.setTitle(title)
        writer.setCreator(f"TelePrompter {__version__}")

        painter = QPainter()
        if not painter.begin(writer):
            return "The PDF could not be created. Check that the folder is writable."

        try:
            _paint_document(painter, writer, script, title, font_family)
        finally:
            painter.end()
    except OSError as exc:
        log.exception("PDF export failed")
        return f"The PDF could not be written.\n\n{exc}"
    return None


def _paint_document(
    painter: QPainter, writer: QPdfWriter, script: Script, title: str, font_family: str
) -> None:
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    page = QRectF(QSizeF(writer.width(), writer.height()))
    width = int(page.width())

    body_font = QFont(font_family)
    body_font.setPointSizeF(BODY_POINT_SIZE)
    body_metrics = QFontMetricsF(body_font)
    line_height = body_metrics.lineSpacing() * 1.35

    title_font = QFont(font_family)
    title_font.setPointSizeF(TITLE_POINT_SIZE)
    title_font.setWeight(QFont.Weight.Bold)
    title_metrics = QFontMetricsF(title_font)

    chapter_font = QFont(font_family)
    chapter_font.setPointSizeF(BODY_POINT_SIZE * 1.25)
    chapter_font.setWeight(QFont.Weight.DemiBold)

    layout = build_layout(
        script,
        width,
        lambda text: round(body_metrics.horizontalAdvance(text)),
        round(body_metrics.horizontalAdvance(" ")),
    )

    ink = QColor(24, 26, 30)
    muted = QColor(120, 126, 134)
    accent = QColor(150, 92, 0)

    y = 0.0
    painter.setFont(title_font)
    painter.setPen(ink)
    painter.drawText(QRectF(0, y, width, title_metrics.height()), Qt.AlignmentFlag.AlignLeft, title)
    y += title_metrics.height() + line_height * 0.4

    painter.setPen(muted)
    painter.drawLine(0, int(y), width, int(y))
    y += line_height

    painter.setFont(body_font)
    for line in layout.lines:
        if y + line_height > page.height():
            writer.newPage()
            y = 0.0

        if line.kind is BlockKind.BLANK:
            y += line_height * 0.5
            continue

        if line.kind is BlockKind.PAUSE:
            painter.setPen(accent)
            middle = y + line_height / 2
            painter.drawLine(0, int(middle), width, int(middle))
            painter.setFont(chapter_font)
            painter.drawText(
                QRectF(0, y, width, line_height),
                Qt.AlignmentFlag.AlignCenter,
                "— PAUSE —",
            )
            painter.setFont(body_font)
            y += line_height * 1.4
            continue

        if line.kind is BlockKind.CHAPTER:
            y += line_height * 0.4
            painter.setFont(chapter_font)
            painter.setPen(accent)
            painter.drawText(
                QRectF(0, y, width, line_height), Qt.AlignmentFlag.AlignLeft, line.text
            )
            painter.setFont(body_font)
            y += line_height * 1.3
            continue

        painter.setPen(ink)
        origin = line_origin_x(line.width, "left", width, 0)
        painter.drawText(
            QRectF(origin, y, width - origin, line_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            line.text,
        )
        y += line_height
