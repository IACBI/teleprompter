"""Presenter notes.

Notes written as ``[[…]]`` never reach the prompter glass. They surface here, on
a small always-on-top window the presenter or the operator can keep on a second
screen.

Every surface in this window renders note text as **plain text**. ``QLabel``
interprets anything that looks like markup as rich text by default, which would
let a script pull in local files through ``<img src="file:///…">``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from ..theme.tokens import RADIUS, SPACE, TYPE, Palette
from .widgets.basic import Separator, label

NO_NOTE = "—"
EMPTY_HINT = "No notes yet.\n\nWrite [[a note like this]] anywhere in your script and it will appear here, never on the prompter."


class NotesWindow(QWidget):
    """Shows the note attached to the line currently being read."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("TelePrompter — Presenter Notes")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setObjectName("AppRoot")
        self.resize(420, 380)
        self.setMinimumSize(300, 240)

        self._palette: Palette | None = None
        self._notes: dict[int, str] = {}
        self._lines: tuple = ()
        self._current_line = -1

        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE.lg, SPACE.lg, SPACE.lg, SPACE.lg)
        column.setSpacing(SPACE.md)

        column.addWidget(label("Now reading", "section"))

        self._current = label(NO_NOTE, wrap=True)
        self._current.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._current.setMinimumHeight(96)
        self._current.setAccessibleName("Current presenter note")
        column.addWidget(self._current)

        column.addWidget(Separator())
        column.addWidget(label("All notes", "section"))

        self._all = QPlainTextEdit()
        self._all.setReadOnly(True)
        self._all.setAccessibleName("All presenter notes")
        self._all.setPlainText(EMPTY_HINT)
        column.addWidget(self._all, 1)

    # ── Theming ───────────────────────────────────────────────────────────────
    def apply_palette(self, palette: Palette, mono_family: str) -> None:
        self._palette = palette
        font = QFont(mono_family)
        font.setPixelSize(TYPE.small)
        self._all.setFont(font)

        current_font = self._current.font()
        current_font.setPixelSize(TYPE.title)
        self._current.setFont(current_font)

        self._restyle_current()

    def _restyle_current(self) -> None:
        palette = self._palette
        if palette is None:
            return
        active = bool(self._notes.get(self._current_line))
        colour = palette.accent if active else palette.text_subtle
        background = palette.surface_raised if active else palette.surface
        border = palette.accent if active else palette.border
        self._current.setStyleSheet(
            f"background: {background}; color: {colour};"
            f" border: 1px solid {border}; border-left: 3px solid {border};"
            f" border-radius: {RADIUS.md}px; padding: {SPACE.md}px;"
        )

    # ── Content ───────────────────────────────────────────────────────────────
    def set_notes(self, notes: dict[int, str], lines) -> None:
        """Replace the full note list. ``notes`` maps line index → note text."""
        self._notes = dict(notes)
        self._lines = lines

        if not notes:
            self._all.setPlainText(EMPTY_HINT)
        else:
            entries = []
            for line_index in sorted(notes):
                context = ""
                if 0 <= line_index < len(lines):
                    context = lines[line_index].text[:56]
                    if len(lines[line_index].text) > 56:
                        context += "…"
                entries.append(f"{context or '(blank line)'}\n    → {notes[line_index]}")
            self._all.setPlainText("\n\n".join(entries))

        self.set_current_line(self._current_line, force=True)

    def set_current_line(self, line_index: int, *, force: bool = False) -> None:
        if line_index == self._current_line and not force:
            return
        self._current_line = line_index
        note = self._notes.get(line_index)
        self._current.setText(note or NO_NOTE)
        self._current.setAccessibleDescription(note or "No note on this line")
        self._restyle_current()
