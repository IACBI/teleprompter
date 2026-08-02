"""Chapter outline.

Long scripts are unreadable as one wall of text. ``[CHAPTER Title]`` markers
turn into this list, which doubles as navigation: clicking a chapter jumps the
prompter there, and the chapter currently being read stays highlighted.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ...core.script import Script
from ...theme.tokens import SPACE, Palette
from .basic import label

EMPTY_HINT = "Add [CHAPTER Title] on its own line to build an outline you can jump through."


class ChapterOutline(QWidget):
    """Lists a script's chapters and emits the block index to jump to."""

    chapterActivated = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._blocks: list[int] = []
        self._palette: Palette | None = None

        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(SPACE.sm)

        column.addWidget(label("Outline", "section"))

        self._list = QListWidget()
        self._list.setAccessibleName("Chapter outline")
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.itemActivated.connect(self._activate)
        self._list.itemClicked.connect(self._activate)
        column.addWidget(self._list, 1)

        self._empty = label(EMPTY_HINT, "caption", wrap=True)
        column.addWidget(self._empty)

        self.set_script(None)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette

    def set_script(self, script: Script | None) -> None:
        self._list.clear()
        self._blocks.clear()

        chapters = script.chapters if script else ()
        for index, chapter in enumerate(chapters, start=1):
            item = QListWidgetItem(f"{index}.  {chapter.title}")
            item.setToolTip(f"Jump to “{chapter.title}”")
            self._list.addItem(item)
            self._blocks.append(chapter.block_index)

        has_chapters = bool(chapters)
        self._list.setVisible(has_chapters)
        self._empty.setVisible(not has_chapters)

    def highlight_block(self, block_index: int) -> None:
        """Select the chapter that contains ``block_index``."""
        current = -1
        for row, start in enumerate(self._blocks):
            if start <= block_index:
                current = row
            else:
                break
        if current >= 0 and self._list.currentRow() != current:
            self._list.blockSignals(True)
            self._list.setCurrentRow(current)
            self._list.blockSignals(False)

    def _activate(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if 0 <= row < len(self._blocks):
            self.chapterActivated.emit(self._blocks[row])
