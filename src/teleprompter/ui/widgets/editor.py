"""The script editor.

A plain text box gives no feedback about whether a tag was typed correctly. This
one numbers its lines, highlights the three script tags as you write them, and
marks the line the prompter is currently reading — so the operator can follow
along in the panel while the presenter reads off the glass.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from ...core.script import CHAPTER_RE, NOTE_RE, PAUSE_RE
from ...theme.tokens import SPACE, TYPE, Palette

PLACEHOLDER = (
    "Type or paste your script here.\n\n"
    "Tags you can use\n"
    "  [PAUSE]            stop scrolling at this point\n"
    "  [CHAPTER Title]    a heading you can jump to\n"
    "  [[note to self]]   private — appears only in the notes window"
)


class TagHighlighter(QSyntaxHighlighter):
    """Colours the three script tags."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._pause = QTextCharFormat()
        self._chapter = QTextCharFormat()
        self._note = QTextCharFormat()

    def apply_palette(self, palette: Palette) -> None:
        self._pause.setForeground(QColor(palette.warning))
        self._pause.setFontWeight(TYPE.weight_semibold)

        self._chapter.setForeground(QColor(palette.accent))
        self._chapter.setFontWeight(TYPE.weight_semibold)

        self._note.setForeground(QColor(palette.info))
        self._note.setFontItalic(True)

        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        stripped = text.strip()
        if PAUSE_RE.match(stripped):
            self.setFormat(0, len(text), self._pause)
        elif CHAPTER_RE.match(stripped):
            self.setFormat(0, len(text), self._chapter)
        for match in NOTE_RE.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self._note)


class _LineNumberArea(QWidget):
    def __init__(self, editor: ScriptEditor) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_width(), 0)

    def paintEvent(self, event) -> None:
        self._editor.paint_line_numbers(event)


class ScriptEditor(QPlainTextEdit):
    """Script entry with line numbers, tag highlighting and a reading marker."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(PLACEHOLDER)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabChangesFocus(True)
        self.setAccessibleName("Script")
        self.setUndoRedoEnabled(True)
        self.setCursorWidth(2)

        self._palette: Palette | None = None
        self._marked_line = -1
        self._numbers = _LineNumberArea(self)
        self._highlighter = TagHighlighter(self.document())

        self.blockCountChanged.connect(lambda _: self._update_margin())
        self.updateRequest.connect(self._on_update_request)
        self._update_margin()

    # ── Theming ───────────────────────────────────────────────────────────────
    def apply_palette(self, palette: Palette, mono_family: str) -> None:
        self._palette = palette
        self._highlighter.apply_palette(palette)
        font = QFont(mono_family)
        font.setPixelSize(TYPE.body_large)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)
        self._numbers.update()

    # ── Reading marker ────────────────────────────────────────────────────────
    def mark_line(self, source_line: int) -> None:
        """Highlight the source line the prompter is currently reading."""
        if source_line == self._marked_line:
            return
        self._marked_line = source_line
        self._numbers.update()

    def go_to_line(self, source_line: int) -> None:
        block = self.document().findBlockByNumber(max(0, source_line))
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()

    # ── Line number gutter ────────────────────────────────────────────────────
    def line_number_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return SPACE.sm * 2 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _on_update_request(self, rect: QRect, dy: int) -> None:
        if dy:
            self._numbers.scroll(0, dy)
        else:
            self._numbers.update(0, rect.y(), self._numbers.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        area = self.contentsRect()
        self._numbers.setGeometry(
            QRect(area.left(), area.top(), self.line_number_width(), area.height())
        )

    def paint_line_numbers(self, event) -> None:
        palette = self._palette
        if palette is None:
            return

        painter = QPainter(self._numbers)
        painter.fillRect(
            event.rect(), QColor(palette.bg if palette.is_dark else palette.surface_overlay)
        )

        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        width = self._numbers.width() - SPACE.sm
        height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                is_marked = number == self._marked_line
                if is_marked:
                    marker = QColor(palette.accent)
                    marker.setAlphaF(0.18)
                    painter.fillRect(QRect(0, int(top), self._numbers.width(), height), marker)
                painter.setPen(QColor(palette.accent if is_marked else palette.text_disabled))
                painter.drawText(
                    QRect(0, int(top), width, height),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    str(number + 1),
                )

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            number += 1
