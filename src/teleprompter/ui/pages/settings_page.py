"""Application settings.

The page this replaced listed the app's own performance features. This one holds
the two decisions that actually belong to the user — whether a system-wide
keyboard hook may be installed, and what the interface looks like — plus the
things you need when something goes wrong.
"""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QWidget

from ... import __author__, __version__
from ...core.settings import UI_THEMES, Settings
from ...services import logging_setup
from ...services.hotkeys import BINDINGS, KEYBOARD_AVAILABLE
from ...storage import paths
from ...theme.tokens import SPACE, Palette
from ..widgets.basic import Card, label, set_variant
from ..widgets.controls import SegmentedControl, ToggleSwitch
from .base import Page

HOTKEY_EXPLANATION = (
    "Global shortcuts let you start and stop the script while another window has "
    "focus — a browser, a slide deck, a video call.\n\n"
    "Turning this on installs a system-wide keyboard hook. While it is active the "
    "keys below are claimed everywhere, so pressing Space in another application "
    "will control the prompter instead of that application. Some antivirus tools "
    "flag keyboard hooks; that is what they are seeing."
)

UNAVAILABLE_NOTE = (
    "Global shortcuts need one extra package.\n\n"
    "Install it with:  pip install keyboard\n"
    "On Linux it also needs permission to read input devices."
)


class SettingsPage(Page):
    """Shortcuts, appearance, diagnostics and about."""

    TITLE = "Settings"
    ICON = "settings"

    hotkeysToggled = Signal(bool)
    resetRequested = Signal()

    def __init__(self, state, playback, parent: QWidget | None = None) -> None:
        super().__init__(state, playback, parent)

        self._hotkey_toggle: ToggleSwitch | None = None
        self._theme_segment: SegmentedControl | None = None

        self.content.addWidget(self._shortcuts_card())
        self.content.addWidget(self._appearance_card())
        self.content.addWidget(self._diagnostics_card())
        self.content.addWidget(self._about_card())
        self.finish()

        self.sync(state.settings)

    # ── Cards ─────────────────────────────────────────────────────────────────
    def _shortcuts_card(self) -> Card:
        card = Card("Global shortcuts", "Control playback without switching windows.")

        if not KEYBOARD_AVAILABLE:
            card.add(label(UNAVAILABLE_NOTE, "muted", wrap=True))
            return card

        self._hotkey_toggle = ToggleSwitch()
        self._hotkey_toggle.toggled.connect(self._on_hotkeys)
        card.add_row("Enable global shortcuts", self._hotkey_toggle, expand=False)

        keys = "     ".join(
            f"{combo.title()} — {action.replace('toggle', 'play or pause')}"
            for action, combo in BINDINGS.items()
        )
        card.add_row("Keys claimed", label(keys, "mono"))

        self.hotkey_status = label("Not enabled.", "caption", wrap=True)
        card.add_row("Status", self.hotkey_status)

        card.add(label(HOTKEY_EXPLANATION, "caption", wrap=True))
        return card

    def _appearance_card(self) -> Card:
        card = Card("Interface", "Applies to this control panel, not the prompter glass.")

        self._theme_segment = SegmentedControl(["Dark", "Light", "System"])
        self._theme_segment.currentChanged.connect(
            lambda index: self._set(ui_theme=UI_THEMES[index])
        )
        card.add_row("Theme", self._theme_segment)
        return card

    def _diagnostics_card(self) -> Card:
        card = Card("Diagnostics", "For when something does not behave.")

        row = QHBoxLayout()
        row.setSpacing(SPACE.sm)

        log_button = QPushButton("Open log folder")
        log_button.setAccessibleName("Open log folder")
        log_button.setToolTip(str(paths.log_dir()))
        log_button.clicked.connect(self._open_logs)
        row.addWidget(log_button)

        config_button = QPushButton("Open settings folder")
        config_button.setAccessibleName("Open settings folder")
        config_button.setToolTip(str(paths.config_dir()))
        config_button.clicked.connect(self._open_config)
        row.addWidget(config_button)

        reset_button = QPushButton("Reset all settings")
        reset_button.setAccessibleName("Reset all settings")
        reset_button.setToolTip("Scripts and saved slots are kept")
        reset_button.clicked.connect(self._reset)
        set_variant(reset_button, "danger")
        row.addWidget(reset_button)

        card.add_layout(row)

        location = logging_setup.log_file()
        card.add(
            label(
                f"Log file: {location}"
                if location
                else "No log file could be created — check folder permissions.",
                "caption",
                wrap=True,
            )
        )
        return card

    def _about_card(self) -> Card:
        card = Card("About")
        card.add_row("Version", label(__version__, "mono"))
        card.add_row("Author", label(__author__, "mono"))
        card.add_row("Licence", label("MIT", "mono"))
        card.add(
            label(
                "Built with Python and Qt for Python (PySide6).",
                "caption",
                wrap=True,
            )
        )
        return card

    # ── Actions ───────────────────────────────────────────────────────────────
    def _on_hotkeys(self, enabled: bool) -> None:
        if self.syncing:
            return
        self.hotkeysToggled.emit(enabled)

    def set_hotkey_status(self, active: bool, message: str) -> None:
        if self._hotkey_toggle is None:
            return
        self.hotkey_status.setText(message)
        palette = self.palette_tokens
        if palette is not None:
            colour = palette.success if active else palette.text_subtle
            self.hotkey_status.setStyleSheet(f"color: {colour};")
        with self.guard():
            self._hotkey_toggle.setChecked(active)

    def _open_logs(self) -> None:
        self._open(paths.log_dir())

    def _open_config(self) -> None:
        self._open(paths.config_dir())

    def _open(self, directory) -> None:
        try:
            paths.ensure_dir(directory)
        except OSError as exc:
            self.notify.emit(f"That folder could not be opened.\n\n{exc}", "error")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            webbrowser.open(directory.as_uri())

    def _reset(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Reset all settings?",
            "Every preference goes back to its default.\n"
            "Your script and saved slots are not touched.",
            QMessageBox.StandardButton.Reset | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm == QMessageBox.StandardButton.Reset:
            self.resetRequested.emit()

    def _set(self, **changes) -> None:
        if not self.syncing:
            self.state.update_settings(**changes)

    # ── Hooks ─────────────────────────────────────────────────────────────────
    def on_palette(self, palette: Palette, ui_font: str, mono_font: str) -> None:
        if self._hotkey_toggle is not None:
            self._hotkey_toggle.apply_palette(palette)
        if self._theme_segment is not None:
            self._theme_segment.apply_palette(palette)

    def sync(self, settings: Settings) -> None:
        with self.guard():
            if self._theme_segment is not None:
                self._theme_segment.set_current_index(
                    UI_THEMES.index(settings.ui_theme), animate=False
                )
            if self._hotkey_toggle is not None:
                self._hotkey_toggle.setChecked(settings.global_hotkeys_enabled)
