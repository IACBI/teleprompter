"""The script page: editor, saved slots, file import and the chapter outline."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...core.settings import Settings
from ...storage import importers
from ...theme.tokens import SPACE, Palette
from ..widgets.basic import IconButton, label
from ..widgets.editor import ScriptEditor
from ..widgets.outline import ChapterOutline
from .base import Page

#: Wait this long after the last keystroke before re-wrapping the prompter.
TYPING_DEBOUNCE_MS = 220


class ScriptPage(Page):
    """Where the script is written, loaded and organised."""

    TITLE = "Script"
    ICON = "script"

    chapterRequested = Signal(int)
    exportRequested = Signal()

    def __init__(self, state, playback, parent: QWidget | None = None) -> None:
        super().__init__(state, playback, parent)

        # The editor wants the whole page, so this one skips the scroll area
        # padding used by the settings pages.
        self.content.setContentsMargins(SPACE.lg, SPACE.lg, SPACE.lg, SPACE.lg)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(TYPING_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._flush_text)

        self.content.addLayout(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self.editor = ScriptEditor()
        self.editor.textChanged.connect(self._debounce.start)
        splitter.addWidget(self.editor)

        self.outline = ChapterOutline()
        self.outline.chapterActivated.connect(self.chapterRequested)
        outline_holder = QWidget()
        outline_layout = QVBoxLayout(outline_holder)
        outline_layout.setContentsMargins(SPACE.md, 0, 0, 0)
        outline_layout.addWidget(self.outline)
        outline_holder.setMinimumWidth(180)
        splitter.addWidget(outline_holder)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([560, 200])
        self.content.addWidget(splitter, 1)

        self._restore_text()
        state.scriptChanged.connect(lambda script: self.outline.set_script(script))
        state.slotsChanged.connect(self._refresh_slots)

    # ── Toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(SPACE.sm)

        row.addWidget(label("Saved script", "muted"))

        self._slots = QComboBox()
        self._slots.setMinimumWidth(180)
        self._slots.setAccessibleName("Saved scripts")
        self._slots.setToolTip("Pick a saved script, then press Open")
        row.addWidget(self._slots, 1)

        self._buttons: dict[str, IconButton] = {}
        actions = (
            ("open", "folder", "Open the selected saved script", self._open_slot),
            ("save", "save", "Save the current script under a name", self._save_slot),
            ("delete", "trash", "Delete the selected saved script", self._delete_slot),
        )
        for key, icon_name, tooltip, handler in actions:
            button = IconButton(icon_name, tooltip)
            button.clicked.connect(handler)
            row.addWidget(button)
            self._buttons[key] = button

        row.addSpacing(SPACE.md)

        for key, icon_name, tooltip, handler in (
            ("undo", "undo", "Undo  (Ctrl+Z)", lambda: self.editor.undo()),
            ("redo", "redo", "Redo  (Ctrl+Y)", lambda: self.editor.redo()),
        ):
            button = IconButton(icon_name, tooltip)
            button.clicked.connect(handler)
            row.addWidget(button)
            self._buttons[key] = button

        row.addSpacing(SPACE.md)

        for key, icon_name, tooltip, handler in (
            ("import", "download", "Import a .txt or .pdf file", self._import_file),
            ("export", "upload", "Export the script as a PDF", self.exportRequested.emit),
        ):
            button = IconButton(icon_name, tooltip)
            button.clicked.connect(handler)
            row.addWidget(button)
            self._buttons[key] = button

        self._refresh_slots()
        return row

    # ── Theming ───────────────────────────────────────────────────────────────
    def on_palette(self, palette: Palette, ui_font: str, mono_font: str) -> None:
        self.editor.apply_palette(palette, mono_font)
        self.outline.apply_palette(palette)
        for button in self._buttons.values():
            button.apply_palette(palette)

    # ── Text flow ─────────────────────────────────────────────────────────────
    def _restore_text(self) -> None:
        text = self.state.script_text
        if not text:
            self.outline.set_script(self.state.script)
            return
        with self.guard():
            self.editor.blockSignals(True)
            self.editor.setPlainText(text)
            self.editor.blockSignals(False)
        self.outline.set_script(self.state.script)

    def _flush_text(self) -> None:
        self.state.set_script_text(self.editor.toPlainText())

    def flush_now(self) -> None:
        """Force a sync — used before saving or exporting."""
        self._debounce.stop()
        self._flush_text()

    def set_text(self, text: str) -> None:
        self.editor.setPlainText(text)
        self.flush_now()

    def mark_reading_line(self, source_line: int) -> None:
        self.editor.mark_line(source_line)

    # ── Slots ─────────────────────────────────────────────────────────────────
    def _refresh_slots(self) -> None:
        current = self._slots.currentText()
        self._slots.blockSignals(True)
        self._slots.clear()
        self._slots.addItems(self.state.slot_names())
        index = self._slots.findText(current)
        if index >= 0:
            self._slots.setCurrentIndex(index)
        self._slots.blockSignals(False)

        has_slots = self._slots.count() > 0
        self._buttons["open"].setEnabled(has_slots)
        self._buttons["delete"].setEnabled(has_slots)
        self._slots.setEnabled(has_slots)
        if not has_slots:
            self._slots.setPlaceholderText("No saved scripts yet")

    def _save_slot(self) -> None:
        self.flush_now()
        suggestion = self._slots.currentText() or "Untitled script"
        name, accepted = QInputDialog.getText(
            self, "Save script", "Name this script:", text=suggestion
        )
        if not accepted or not name.strip():
            return
        if self.state.save_slot(name, self.editor.toPlainText()):
            self._refresh_slots()
            index = self._slots.findText(name.strip())
            if index >= 0:
                self._slots.setCurrentIndex(index)
            self.notify.emit(f"Saved as “{name.strip()}”.", "success")
        else:
            self.notify.emit("That script could not be saved — it may be too large.", "error")

    def _open_slot(self) -> None:
        name = self._slots.currentText()
        text = self.state.slot_text(name)
        if text is None:
            return
        if self.editor.toPlainText().strip() and text != self.editor.toPlainText():
            confirm = QMessageBox.question(
                self,
                "Replace the current script?",
                f"Opening “{name}” will replace what is in the editor.",
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm != QMessageBox.StandardButton.Open:
                return
        self.set_text(text)
        self.notify.emit(f"Opened “{name}”.", "info")

    def _delete_slot(self) -> None:
        name = self._slots.currentText()
        if not name:
            return
        confirm = QMessageBox.question(
            self,
            "Delete saved script?",
            f"“{name}” will be removed. This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if self.state.delete_slot(name):
            self._refresh_slots()
            self.notify.emit(f"Deleted “{name}”.", "info")

    # ── Import ────────────────────────────────────────────────────────────────
    def _import_file(self) -> None:
        if importers.pdf_available():
            filters = (
                "Scripts (*.txt *.md *.pdf);;Text files (*.txt *.md);;"
                "PDF files (*.pdf);;All files (*)"
            )
        else:
            filters = "Text files (*.txt *.md);;All files (*)"

        path, _ = QFileDialog.getOpenFileName(self, "Import a script", "", filters)
        if not path:
            return

        result = importers.read_script_file(path)
        if not result.ok:
            QMessageBox.warning(self, "This file could not be imported", result.error or "")
            return

        self.set_text(result.text)
        self.state.remember_file(path)
        if result.warning:
            self.notify.emit(result.warning, "warning")
        else:
            self.notify.emit("Script imported.", "success")

    def sync(self, settings: Settings) -> None:
        return
