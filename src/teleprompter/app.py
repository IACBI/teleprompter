"""Application bootstrap.

Order matters here. High-DPI policy has to be set before the ``QApplication``
exists, logging has to be running before anything can fail, and the excepthooks
have to be installed before the first window is built — a packaged build has no
console to print a traceback to.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QApplication

from . import APP_ID, APP_NAME, ORG_NAME, __version__
from .core.settings import Settings
from .resources import icons
from .services import logging_setup
from .state import AppState, PlaybackController
from .storage import store
from .storage.store import LoadProblem
from .theme import build_stylesheet, ensure_glyphs, palette_for
from .theme.tokens import MONO_FONT_CANDIDATES, UI_FONT_CANDIDATES, Palette
from .ui.main_window import MainWindow

log = logging.getLogger(__name__)


def _configure_high_dpi() -> None:
    """Keep fractional display scaling exact.

    Qt 6 enables high-DPI scaling and high-DPI pixmaps on its own. What it still
    does by default is round the scale factor, so a 150% display renders at
    200% and everything looks oversized. Pass-through keeps the real factor.
    Must run before the QApplication exists.
    """
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


def _set_windows_app_id() -> None:
    """Give Windows a stable identity so the taskbar shows our own icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        log.debug("Could not set the Windows application id", exc_info=True)


def _first_available_font(candidates: tuple[str, ...], fallback: str) -> str:
    installed = set(QFontDatabase.families())
    for name in candidates:
        if name in installed:
            return name
    return fallback


def _system_prefers_dark() -> bool:
    hints = QGuiApplication.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    if scheme is None:
        return True
    return scheme() != Qt.ColorScheme.Light


def resolve_palette(settings: Settings) -> Palette:
    return palette_for(settings.ui_theme, _system_prefers_dark())


def apply_theme(app: QApplication, settings: Settings, ui_font: str, mono_font: str) -> Palette:
    """Rebuild and install the global stylesheet for the current theme."""
    palette = resolve_palette(settings)
    glyphs = ensure_glyphs(palette)
    app.setStyleSheet(build_stylesheet(palette, ui_font, mono_font, glyphs))
    return palette


def _arrange_windows(panel: MainWindow) -> None:
    """Place the panel and the prompter side by side on first run."""
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return
    area = screen.availableGeometry()

    panel_width = min(max(panel.minimumWidth(), 1000), int(area.width() * 0.46))
    panel_height = min(panel.height(), area.height() - 60)
    panel.resize(panel_width, panel_height)
    panel.move(area.x() + 24, area.y() + (area.height() - panel_height) // 2)

    prompter = panel.prompter
    gap = 16
    x = area.x() + 24 + panel_width + gap
    width = max(prompter.minimumWidth(), area.right() - x - 24)
    height = min(int(area.height() * 0.72), area.height() - 60)
    prompter.resize(width, height)
    prompter.move(x, area.y() + (area.height() - height) // 2)


def _report_load_problem(window: MainWindow, result: store.LoadResult) -> None:
    if result.problem is LoadProblem.RECOVERED_FROM_BACKUP:
        window.toast(
            "Your settings file was damaged, so the previous good copy was restored.",
            "warning",
        )
    elif result.problem is LoadProblem.CORRUPT:
        window.toast(
            "Your saved settings and scripts could not be read and have been reset. "
            "The details are in the log file.",
            "error",
        )
        log.error("State load failed: %s", result.detail)
    elif result.detail == "migrated from 1.x":
        window.toast("Your scripts were carried over from the previous version.", "success")


def main() -> int:
    """Entry point for the ``teleprompter`` command."""
    logging_setup.setup()
    logging_setup.install_excepthooks()
    log.info("Starting %s %s on %s", APP_NAME, __version__, sys.platform)

    _configure_high_dpi()
    _set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")

    result = store.load()
    state = AppState(result.data)
    playback = PlaybackController(state)

    ui_font = _first_available_font(UI_FONT_CANDIDATES, app.font().family())
    mono_font = _first_available_font(MONO_FONT_CANDIDATES, "monospace")

    icon = icons.app_icon()
    app.setWindowIcon(icon)

    window = MainWindow(state, playback)
    for target in (window, window.prompter, window.notes):
        target.setWindowIcon(icon)

    def refresh_theme(settings: Settings = state.settings) -> None:
        palette = apply_theme(app, settings, ui_font, mono_font)
        window.apply_palette(palette, ui_font, mono_font)

    refresh_theme()
    state.settingsChanged.connect(
        lambda settings: refresh_theme(settings) if _theme_changed(settings) else None
    )

    _arrange_windows(window)
    window.show()
    window.prompter.show()

    _report_load_problem(window, result)
    window.maybe_show_welcome()

    app.aboutToQuit.connect(window.shutdown)
    return app.exec()


_last_ui_theme: str | None = None


def _theme_changed(settings: Settings) -> bool:
    """Only rebuild the stylesheet when the interface theme actually moved."""
    global _last_ui_theme
    if settings.ui_theme == _last_ui_theme:
        return False
    _last_ui_theme = settings.ui_theme
    return True


if __name__ == "__main__":
    sys.exit(main())
