"""Tag highlighting in the script editor.

QSyntaxHighlighter.setFormat counts UTF-16 code units, while the parsers count
code points. The two agree only for text in the Basic Multilingual Plane, so
these tests put non-BMP characters (emoji) before the tags they check.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="the GUI layer needs PySide6")

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication

from teleprompter.theme import DARK
from teleprompter.ui.widgets.editor import TagHighlighter

pytestmark = pytest.mark.gui


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


def _highlight(qapp, text: str) -> list:
    document = QTextDocument()
    highlighter = TagHighlighter(document)
    highlighter.apply_palette(DARK)
    document.setPlainText(text)
    highlighter.rehighlight()
    ranges = document.firstBlock().layout().formats()
    return [(r.start, r.length, r.format.fontItalic()) for r in ranges]


def test_a_note_after_an_emoji_is_formatted_at_its_utf16_offset(qapp):
    # "😀" is one code point but two UTF-16 units, so the note starts at 9, not 8.
    line = "😀 Hello [[note]]"
    assert line.index("[[") == 8
    notes = [r for r in _highlight(qapp, line) if r[2]]
    assert notes == [(9, 8, True)]


def test_a_note_after_several_emoji_and_before_a_second_note(qapp):
    line = "🎙🎙 [[one]] 😀 mid [[two]]"
    notes = [r for r in _highlight(qapp, line) if r[2]]
    # Each emoji here is outside the BMP, so takes two units: 2+2 for the first
    # pair, 9 for " [[one]] ", 2 for the smiley and 5 for " mid ".
    assert notes == [(5, 7, True), (4 + 9 + 2 + 5, 7, True)]


def test_a_chapter_line_with_an_emoji_is_formatted_to_its_utf16_end(qapp):
    line = "[CHAPTER Intro 😀]"
    ranges = _highlight(qapp, line)
    covered = sum(length for _, length, _ in ranges)
    assert covered == len(line.encode("utf-16-le")) // 2
