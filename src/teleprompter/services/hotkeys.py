"""System-wide hotkeys.

The optional ``keyboard`` package installs a low-level OS keyboard hook and
fires its callbacks on its own listener thread. Calling widget or timer methods
from that thread violates Qt's thread affinity rules, so every callback here
does exactly one thing: emit a signal. Qt delivers it to the GUI thread through
a queued connection.

The hook is **opt-in**. It observes the whole keyboard stream while active, and
that is not something to switch on without the user asking for it.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)

try:
    import keyboard as _keyboard

    KEYBOARD_AVAILABLE = True
except Exception:
    _keyboard = None  # type: ignore[assignment]
    KEYBOARD_AVAILABLE = False


#: Action name → key combination. Kept deliberately small: the fewer keys the
#: hook claims globally, the less it interferes with other applications.
BINDINGS: dict[str, str] = {
    "toggle": "space",
    "reset": "r",
}


class HotkeyService(QObject):
    """Registers global hotkeys and reports what actually happened."""

    #: Emitted on the GUI thread with an action name from :data:`BINDINGS`.
    triggered = Signal(str)
    #: ``(active, human readable status)`` — drives the settings page label.
    statusChanged = Signal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._handles: list[Any] = []
        self._active = False
        self._status = "Not enabled."

    @property
    def available(self) -> bool:
        return KEYBOARD_AVAILABLE

    @property
    def active(self) -> bool:
        return self._active

    @property
    def status(self) -> str:
        return self._status

    def set_enabled(self, enabled: bool) -> bool:
        """Turn the global hook on or off. Returns the resulting active state."""
        if enabled:
            return self._register()
        self._unregister()
        return False

    # ── Internals ─────────────────────────────────────────────────────────────
    def _register(self) -> bool:
        if self._active:
            return True
        if not KEYBOARD_AVAILABLE:
            self._set_status(False, "Unavailable — install it with:  pip install keyboard")
            return False

        registered: list[str] = []
        for action, combination in BINDINGS.items():
            try:
                handle = _keyboard.add_hotkey(
                    combination,
                    self._make_emitter(action),
                    suppress=False,
                )
            except Exception as exc:
                log.warning("Could not bind global hotkey %r: %s", combination, exc)
                continue
            self._handles.append(handle)
            registered.append(combination.title())

        if not registered:
            self._unregister()
            self._set_status(
                False,
                "Registration failed. On Linux this usually needs elevated permissions.",
            )
            return False

        self._active = True
        self._set_status(True, f"Active — {' and '.join(registered)} work in any application.")
        return True

    def _make_emitter(self, action: str):
        """Return a callback that only touches a signal — never a widget."""

        def emit() -> None:
            self.triggered.emit(action)

        return emit

    def _unregister(self) -> None:
        for handle in self._handles:
            try:
                _keyboard.remove_hotkey(handle)
            except Exception:
                log.debug("Hotkey handle could not be removed", exc_info=True)
        self._handles.clear()
        if self._active:
            self._active = False
            self._set_status(False, "Not enabled.")

    def _set_status(self, active: bool, message: str) -> None:
        self._status = message
        self.statusChanged.emit(active, message)

    def shutdown(self) -> None:
        """Release the OS hook. Called from the application teardown."""
        self._unregister()
