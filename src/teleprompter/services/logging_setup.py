"""Logging and crash reporting.

A packaged, windowed build has no console, so a traceback printed to stderr is a
traceback nobody will ever see. Everything is written to a rotating file
instead, and an unhandled exception raises a dialog that tells the user where
that file is.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
import threading
import traceback
from pathlib import Path
from types import TracebackType

from ..storage import paths

LOG_FILENAME = "teleprompter.log"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 3

_FORMAT = "%(asctime)s %(levelname)-7s %(name)-28s %(message)s"

_log_path: Path | None = None
_crash_reported = False


def log_file() -> Path | None:
    """Path of the active log file, or None if file logging never started."""
    return _log_path


def setup(level: int = logging.INFO, *, to_console: bool = True) -> Path | None:
    """Install the root logging configuration. Safe to call more than once."""
    global _log_path

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(_FORMAT)

    try:
        directory = paths.ensure_dir(paths.log_dir())
        target = directory / LOG_FILENAME
        file_handler = logging.handlers.RotatingFileHandler(
            target, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        _log_path = target
    except OSError:
        # A read-only or missing home directory must not stop the app.
        _log_path = None

    if to_console and sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        root.addHandler(console)

    if not root.handlers:
        root.addHandler(logging.NullHandler())

    return _log_path


def format_exception(
    exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
) -> str:
    return "".join(traceback.format_exception(exc_type, exc, tb))


def install_excepthooks() -> None:
    """Route unhandled exceptions — on any thread — to the log and a dialog."""
    logger = logging.getLogger("teleprompter.crash")

    def handle(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        details = format_exception(exc_type, exc, tb)
        logger.critical("Unhandled exception\n%s", details)
        _show_crash_dialog(details)

    sys.excepthook = handle

    def handle_thread(args: threading.ExceptHookArgs) -> None:
        if issubclass(args.exc_type, SystemExit):
            return
        logger.critical(
            "Unhandled exception on thread %s\n%s",
            args.thread.name if args.thread else "?",
            format_exception(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = handle_thread


def _show_crash_dialog(details: str) -> None:
    """Best-effort GUI report. Never raises — it runs while already failing."""
    global _crash_reported
    if _crash_reported:
        return

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            return
        _crash_reported = True

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("TelePrompter — Unexpected Error")
        box.setText("Something went wrong.\n\nYour script is still in the editor.")
        location = f"\n\nA full report was written to:\n{_log_path}" if _log_path else ""
        box.setInformativeText(
            f"{details.strip().splitlines()[-1] if details.strip() else ''}{location}"
        )
        box.setDetailedText(details)
        box.setStandardButtons(QMessageBox.StandardButton.Close)
        box.exec()
    except Exception:
        logging.getLogger("teleprompter.crash").debug("Crash dialog unavailable", exc_info=True)
    finally:
        _crash_reported = False
