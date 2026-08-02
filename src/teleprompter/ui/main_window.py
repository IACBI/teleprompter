"""The control panel.

A navigation rail on the left, one page at a time in the middle, and the
transport bar pinned along the bottom so playback is reachable wherever you are.

This class is the only place that knows about all the moving parts: it owns the
prompter and notes windows, the optional hotkey and microphone services, the
autosave timer, and the shutdown sequence.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.settings import Settings
from ..resources import icons
from ..services.audio import AudioMonitor
from ..services.hotkeys import HotkeyService
from ..state import AppState, PlaybackController
from ..theme.tokens import MIN_HIT_TARGET, SPACE, Palette
from . import export
from .notes_window import NotesWindow
from .onboarding import SAMPLE_SCRIPT, WelcomeDialog
from .pages import (
    AudioPage,
    DisplayPage,
    PrompterPage,
    ScriptPage,
    SettingsPage,
    TimingPage,
)
from .prompter_window import PrompterWindow
from .transport_bar import TransportBar
from .widgets.basic import Separator, label
from .widgets.feedback import ToastHost

log = logging.getLogger(__name__)

NAV_WIDTH = 188

#: Nothing is lost to a crash for longer than this.
AUTOSAVE_INTERVAL_MS = 45_000
#: …and a burst of typing settles into one write rather than many.
AUTOSAVE_IDLE_MS = 6_000


class MainWindow(QWidget):
    """The control panel window."""

    def __init__(self, state: AppState, playback: PlaybackController) -> None:
        super().__init__()
        self._state = state
        self._playback = playback
        self._palette: Palette | None = None
        self._ui_font = "Segoe UI"
        self._mono_font = "Consolas"

        self.setObjectName("AppRoot")
        self.setWindowTitle("TelePrompter — Control Panel")
        self.setMinimumSize(880, 620)
        self.resize(1040, 760)

        # ── Owned windows ─────────────────────────────────────────────────────
        self.prompter = PrompterWindow(state, playback)
        self.notes = NotesWindow()
        self.prompter.attach_notes(self.notes)

        # ── Services ──────────────────────────────────────────────────────────
        self.hotkeys = HotkeyService(self)
        self.hotkeys.triggered.connect(self._on_hotkey)
        self.hotkeys.statusChanged.connect(self._on_hotkey_status)

        self.audio = AudioMonitor(self)
        self.audio.gateChanged.connect(playback.set_gate)
        self.audio.levelChanged.connect(self._on_audio_level)
        self.audio.failed.connect(self._on_audio_failed)

        # ── Shell ─────────────────────────────────────────────────────────────
        self._build_ui()
        self._install_shortcuts()

        self.toasts = ToastHost(self)

        # ── Autosave ──────────────────────────────────────────────────────────
        self._autosave = QTimer(self)
        self._autosave.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave.timeout.connect(self._save_quietly)
        self._autosave.start()

        self._idle_save = QTimer(self)
        self._idle_save.setSingleShot(True)
        self._idle_save.setInterval(AUTOSAVE_IDLE_MS)
        self._idle_save.timeout.connect(self._save_quietly)

        # ── Wiring ────────────────────────────────────────────────────────────
        state.settingsChanged.connect(self._on_settings_changed)
        state.scriptChanged.connect(lambda _s: self._idle_save.start())
        playback.positionChanged.connect(self._sync_editor_marker)
        playback.pausedAtMarker.connect(
            lambda: self.toasts.show_message("Paused at a [PAUSE] marker.", "info")
        )
        playback.finished.connect(
            lambda: self.toasts.show_message("Reached the end of the script.", "success")
        )

        self._apply_service_settings(state.settings, first_run=True)

    # ══ Construction ══════════════════════════════════════════════════════════
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_nav())

        right = QWidget()
        column = QVBoxLayout(right)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self._stack = QStackedWidget()
        column.addWidget(self._stack, 1)

        self.transport = TransportBar(self._state, self._playback)
        self.transport.previousChapter.connect(lambda: self._jump_chapter(-1))
        self.transport.nextChapter.connect(lambda: self._jump_chapter(1))
        column.addWidget(self.transport)

        root.addWidget(right, 1)

        self._build_pages()

    def _build_nav(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("NavRail")
        rail.setFixedWidth(NAV_WIDTH)

        column = QVBoxLayout(rail)
        column.setContentsMargins(SPACE.md, SPACE.lg, SPACE.md, SPACE.lg)
        column.setSpacing(SPACE.xs)

        self._brand = label("TelePrompter", "title")
        self._brand.setContentsMargins(SPACE.sm, 0, 0, SPACE.md)
        column.addWidget(self._brand)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: list[QPushButton] = []
        self._nav_group.idClicked.connect(self._show_page)

        self._nav_container = column
        column.addStretch(1)
        column.addWidget(Separator())

        self._hint = label("Ctrl+Enter plays · Ctrl+R rewinds", "caption", wrap=True)
        self._hint.setContentsMargins(SPACE.sm, SPACE.sm, SPACE.sm, 0)
        column.addWidget(self._hint)

        return rail

    def _build_pages(self) -> None:
        self.script_page = ScriptPage(self._state, self._playback)
        self.display_page = DisplayPage(self._state, self._playback)
        self.prompter_page = PrompterPage(self._state, self._playback, self.prompter, self.notes)
        self.timing_page = TimingPage(self._state, self._playback)
        self.audio_page = AudioPage(self._state, self._playback)
        self.settings_page = SettingsPage(self._state, self._playback)

        self.pages = [
            self.script_page,
            self.display_page,
            self.prompter_page,
            self.timing_page,
            self.audio_page,
            self.settings_page,
        ]

        for index, page in enumerate(self.pages):
            self._stack.addWidget(page)
            page.notify.connect(self.toast)

            button = QPushButton(f"  {page.TITLE}")
            button.setCheckable(True)
            button.setMinimumHeight(MIN_HIT_TARGET + 4)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(page.TITLE)
            button.setToolTip(f"{page.TITLE}   (Ctrl+{index + 1})")
            self._nav_group.addButton(button, index)
            self._nav_container.insertWidget(index + 1, button)
            self._nav_buttons.append(button)

        self.script_page.chapterRequested.connect(self.prompter.seek_to_block)
        self.script_page.exportRequested.connect(self._export_pdf)
        self.settings_page.hotkeysToggled.connect(self._on_hotkeys_toggled)
        self.settings_page.resetRequested.connect(self._reset_settings)

        self._nav_buttons[0].setChecked(True)
        self._stack.setCurrentIndex(0)

    def _install_shortcuts(self) -> None:
        def bind(sequence: str, handler) -> None:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(handler)

        bind("Ctrl+Return", self._playback.toggle)
        bind("Ctrl+R", self._playback.reset)
        bind("Ctrl+Left", lambda: self._jump_chapter(-1))
        bind("Ctrl+Right", lambda: self._jump_chapter(1))
        bind("Ctrl+S", self._save_now)
        bind("F5", self._show_prompter)
        bind("F11", self.prompter.toggle_fullscreen)
        for index in range(6):
            bind(f"Ctrl+{index + 1}", lambda i=index: self._select_page(i))

    # ══ Theming ═══════════════════════════════════════════════════════════════
    def apply_palette(self, palette: Palette, ui_font: str, mono_font: str) -> None:
        self._palette = palette
        self._ui_font = ui_font
        self._mono_font = mono_font

        for index, page in enumerate(self.pages):
            page.apply_palette(palette, ui_font, mono_font)
            self._nav_buttons[index].setIcon(icons.icon(page.ICON, palette.text_muted, 18))
            self._nav_buttons[index].setIconSize(icons.icon_size(18))

        self.transport.apply_palette(palette)
        self.prompter.apply_palette(palette)
        self.notes.apply_palette(palette, mono_font)
        self.toasts.apply_palette(palette)
        self._highlight_nav()

    def _highlight_nav(self) -> None:
        if self._palette is None:
            return
        current = self._stack.currentIndex()
        for index, button in enumerate(self._nav_buttons):
            colour = self._palette.accent if index == current else self._palette.text_muted
            button.setIcon(icons.icon(self.pages[index].ICON, colour, 18))

    # ══ Navigation ════════════════════════════════════════════════════════════
    def _show_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._highlight_nav()

    def _select_page(self, index: int) -> None:
        if 0 <= index < len(self._nav_buttons):
            self._nav_buttons[index].setChecked(True)
            self._show_page(index)

    def _jump_chapter(self, direction: int) -> None:
        chapters = self._state.script.chapters
        if not chapters:
            self.toast("This script has no [CHAPTER] markers yet.", "info")
            return

        current_block = self.prompter.current_block_index()
        positions = [chapter.block_index for chapter in chapters]

        if direction < 0:
            candidates = [p for p in positions if p < current_block - 1]
            target = candidates[-1] if candidates else positions[0]
        else:
            candidates = [p for p in positions if p > current_block]
            target = candidates[0] if candidates else positions[-1]

        self.prompter.seek_to_block(target)
        title = next(c.title for c in chapters if c.block_index == target)
        self.toast(f"Jumped to “{title}”.", "info")

    # ══ Services ══════════════════════════════════════════════════════════════
    def _on_settings_changed(self, settings: Settings) -> None:
        for page in self.pages:
            page.sync(settings)
        self._apply_service_settings(settings)
        self._idle_save.start()

    def _apply_service_settings(self, settings: Settings, *, first_run: bool = False) -> None:
        if settings.mic_enabled and not self.audio.running:
            if not self.audio.start():
                self._state.update_settings(mic_enabled=False)
            else:
                self.audio_page.set_status("Listening")
        elif not settings.mic_enabled and self.audio.running:
            self.audio.stop()
            self._playback.set_gate(1.0)
            self.audio_page.set_status("Off")

        if settings.global_hotkeys_enabled != self.hotkeys.active:
            active = self.hotkeys.set_enabled(settings.global_hotkeys_enabled)
            if settings.global_hotkeys_enabled and not active:
                self._state.update_settings(global_hotkeys_enabled=False)

        if first_run and settings.prompter_screen:
            for screen in QGuiApplication.screens():
                if screen.name() == settings.prompter_screen:
                    self.prompter.move_to_screen(screen, settings.prompter_fullscreen)
                    break

    def _on_hotkeys_toggled(self, enabled: bool) -> None:
        self._state.update_settings(global_hotkeys_enabled=enabled)

    def _on_hotkey(self, action: str) -> None:
        """Runs on the GUI thread — the service marshals it across for us."""
        if action == "toggle":
            self._playback.toggle()
        elif action == "reset":
            self._playback.reset()

    def _on_hotkey_status(self, active: bool, message: str) -> None:
        self.settings_page.set_hotkey_status(active, message)
        if active:
            self.toast("Global shortcuts are now active in every application.", "warning")

    def _on_audio_level(self, level: float) -> None:
        self.audio_page.set_level(level)

    def _on_audio_failed(self, message: str) -> None:
        self.toast(message, "error")
        self._state.update_settings(mic_enabled=False)

    # ══ Actions ═══════════════════════════════════════════════════════════════
    def toast(self, text: str, severity: str = "info") -> None:
        self.toasts.show_message(text, severity)

    def maybe_show_welcome(self) -> None:
        """Introduce the app once, on a first run with nothing to read."""
        if self._state.settings.onboarding_done or self._palette is None:
            return
        if not self._state.script.is_empty:
            # There is already a script to work with; skip the introduction.
            self._state.update_settings(onboarding_done=True)
            return

        dialog = WelcomeDialog(self._palette, self)
        dialog.exec()
        self._state.update_settings(onboarding_done=True)
        if dialog.wants_sample:
            self.script_page.set_text(SAMPLE_SCRIPT)
            self.toast("Sample script loaded — press Play to see how it reads.", "info")

    def _show_prompter(self) -> None:
        self.prompter.show()
        self.prompter.raise_()

    def _sync_editor_marker(self, _scroll_y: float) -> None:
        block_index = self.prompter.current_block_index()
        blocks = self._state.script.blocks
        if 0 <= block_index < len(blocks):
            self.script_page.mark_reading_line(blocks[block_index].source_line)

    def _export_pdf(self) -> None:
        self.script_page.flush_now()
        if self._state.script.is_empty:
            self.toast("There is nothing to export yet.", "warning")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export script as PDF", "script.pdf", "PDF files (*.pdf)"
        )
        if not path:
            return

        error = export.export_script_to_pdf(self._state.script, path, font_family=self._ui_font)
        if error:
            self.toast(error, "error")
        else:
            self.toast(f"Exported to {path}", "success")

    def _reset_settings(self) -> None:
        self._state.reset_settings()
        self.toast("Settings restored to their defaults.", "info")

    def _save_quietly(self) -> None:
        self.script_page.flush_now()
        error = self._state.save()
        if error:
            self.toast(error, "error")

    def _save_now(self) -> None:
        self._save_quietly()
        self.toast("Saved.", "success")

    # ══ Window events ═════════════════════════════════════════════════════════
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.toasts.parent_resized()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.toasts.parent_resized()

    def shutdown(self) -> None:
        """Release everything this window owns. Called from the app teardown."""
        self._autosave.stop()
        self._idle_save.stop()
        self._playback.shutdown()
        self.audio.stop()
        self.hotkeys.shutdown()
        self.script_page.flush_now()
        error = self._state.save()
        if error:
            log.error("Final save failed: %s", error)
        self.notes.close()
        self.prompter.close()

    def closeEvent(self, event) -> None:
        self.shutdown()
        event.accept()
