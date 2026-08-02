"""Platform-appropriate application directories.

Resolved without Qt so persistence can be tested headlessly, and so the crash
handler can find the log directory even if Qt itself failed to start.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIRNAME = "TelePrompter"

#: Where the pre-2.0 single-file build kept its data.
LEGACY_SAVE_FILE = Path.home() / ".teleprompter.json"


def _base_dir(kind: str) -> Path:
    if sys.platform == "win32":
        root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        return Path(root) if root else Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / ("Logs" if kind == "log" else "Application Support")
    if kind == "log":
        root = os.environ.get("XDG_STATE_HOME")
        return Path(root) if root else Path.home() / ".local" / "state"
    root = os.environ.get("XDG_CONFIG_HOME")
    return Path(root) if root else Path.home() / ".config"


def config_dir() -> Path:
    """Directory holding ``state.json``. Created on demand by the caller."""
    return _base_dir("config") / APP_DIRNAME


def log_dir() -> Path:
    """Directory holding rotating log files."""
    base = _base_dir("log") / APP_DIRNAME
    return base if sys.platform == "darwin" else base / "logs"


def state_file() -> Path:
    return config_dir() / "state.json"


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing; returns it for chaining."""
    path.mkdir(parents=True, exist_ok=True)
    return path
