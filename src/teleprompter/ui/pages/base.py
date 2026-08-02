"""Shared page scaffolding.

Pages scroll. A control panel that cannot scroll is a control panel that hides
its bottom half on a 768-pixel laptop screen.
"""

from __future__ import annotations

from contextlib import contextmanager

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ...core.settings import Settings
from ...state import AppState, PlaybackController
from ...theme.tokens import SPACE, Palette


class Page(QWidget):
    """Base class for a control-panel page."""

    #: Ask the shell to show a transient message.
    notify = Signal(str, str)  # text, severity

    TITLE = ""
    ICON = "info"
    SUBTITLE = ""

    def __init__(
        self, state: AppState, playback: PlaybackController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.playback = playback
        self.palette_tokens: Palette | None = None
        self._syncing = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(self._scroll)

        holder = QWidget()
        self.content = QVBoxLayout(holder)
        self.content.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.xl)
        self.content.setSpacing(SPACE.lg)
        self._scroll.setWidget(holder)

        self.setAccessibleName(self.TITLE or type(self).__name__)

    def finish(self) -> None:
        """Called once after a subclass has added its cards."""
        self.content.addStretch(1)

    @contextmanager
    def guard(self):
        """Suppress change handlers while pushing values into widgets."""
        previous, self._syncing = self._syncing, True
        try:
            yield
        finally:
            self._syncing = previous

    @property
    def syncing(self) -> bool:
        return self._syncing

    # ── Hooks ─────────────────────────────────────────────────────────────────
    def apply_palette(self, palette: Palette, ui_font: str, mono_font: str) -> None:
        self.palette_tokens = palette
        self.on_palette(palette, ui_font, mono_font)

    def on_palette(self, palette: Palette, ui_font: str, mono_font: str) -> None:
        """Retint anything that paints itself."""

    def sync(self, settings: Settings) -> None:
        """Push settings into this page's widgets."""
