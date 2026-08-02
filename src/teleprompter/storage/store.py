"""Durable application state.

Three properties matter more than anything else here, because losing a
presenter's script minutes before they go live is unacceptable:

1. **Atomic writes.** Data is written to a sibling temp file, flushed to the
   platter, then moved into place with :func:`os.replace`. A crash mid-save
   leaves either the old file or the new one, never a truncated one.
2. **A backup generation.** The previous good state is kept as ``.bak`` and
   used automatically if the primary file is unreadable.
3. **Loud failure.** When both copies are unusable the loader says so via
   :attr:`LoadResult.problem` instead of silently returning empty state.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from ..core.settings import RehearsalRun, ScriptSlot, Settings
from . import paths

SCHEMA_VERSION = 2

#: A saved script larger than this is almost certainly a mistake; refuse to
#: grow the state file without bound.
MAX_SLOT_CHARS = 4_000_000
MAX_SLOTS = 200
MAX_RECENT_FILES = 12
MAX_REHEARSALS = 20


class LoadProblem(Enum):
    """Why a load did not return the primary file's contents."""

    NONE = "none"
    MISSING = "missing"
    RECOVERED_FROM_BACKUP = "recovered_from_backup"
    CORRUPT = "corrupt"
    UNREADABLE = "unreadable"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AppData:
    """Everything that survives a restart."""

    settings: Settings = field(default_factory=Settings)
    slots: dict[str, ScriptSlot] = field(default_factory=dict)
    last_text: str = ""
    recent_files: list[str] = field(default_factory=list)
    rehearsals: list[RehearsalRun] = field(default_factory=list)

    # ── Slot helpers ──────────────────────────────────────────────────────────
    def save_slot(self, name: str, text: str) -> bool:
        """Store ``text`` under ``name``. Returns False if it was rejected."""
        name = name.strip()
        if not name or len(text) > MAX_SLOT_CHARS:
            return False
        if name not in self.slots and len(self.slots) >= MAX_SLOTS:
            return False
        self.slots[name] = ScriptSlot(name=name, text=text, updated_at=_utc_now())
        return True

    def delete_slot(self, name: str) -> bool:
        return self.slots.pop(name, None) is not None

    def remember_file(self, path: str) -> None:
        """Push ``path`` to the front of the recent-files list."""
        self.recent_files = [path] + [p for p in self.recent_files if p != path]
        del self.recent_files[MAX_RECENT_FILES:]

    def add_rehearsal(self, run: RehearsalRun) -> None:
        self.rehearsals.insert(0, run)
        del self.rehearsals[MAX_REHEARSALS:]

    # ── Serialisation ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "saved_at": _utc_now(),
            "settings": self.settings.to_dict(),
            "slots": {
                name: {"text": slot.text, "updated_at": slot.updated_at}
                for name, slot in self.slots.items()
            },
            "last_text": self.last_text,
            "recent_files": self.recent_files,
            "rehearsals": [
                {
                    "finished_at": r.finished_at,
                    "duration_seconds": r.duration_seconds,
                    "word_count": r.word_count,
                    "chapter_seconds": [list(pair) for pair in r.chapter_seconds],
                }
                for r in self.rehearsals
            ],
        }

    @classmethod
    def from_dict(cls, data: Any) -> AppData:
        """Rebuild from untrusted JSON, tolerating anything malformed."""
        if not isinstance(data, dict):
            return cls()

        version = data.get("version")
        if not isinstance(version, int) or version < SCHEMA_VERSION:
            data = migrate(data)

        return cls(
            settings=Settings.from_dict(data.get("settings")),
            slots=_slots_from(data.get("slots")),
            last_text=data.get("last_text") if isinstance(data.get("last_text"), str) else "",
            recent_files=[p for p in _as_list(data.get("recent_files")) if isinstance(p, str)][
                :MAX_RECENT_FILES
            ],
            rehearsals=_rehearsals_from(data.get("rehearsals")),
        )


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _slots_from(value: Any) -> dict[str, ScriptSlot]:
    if not isinstance(value, dict):
        return {}
    slots: dict[str, ScriptSlot] = {}
    for name, payload in value.items():
        if not isinstance(name, str) or len(slots) >= MAX_SLOTS:
            continue
        if isinstance(payload, str):  # v1 shape: name → text
            text, updated = payload, ""
        elif isinstance(payload, dict) and isinstance(payload.get("text"), str):
            text = payload["text"]
            stamp = payload.get("updated_at")
            updated = stamp if isinstance(stamp, str) else ""
        else:
            continue
        slots[name] = ScriptSlot(name=name, text=text[:MAX_SLOT_CHARS], updated_at=updated)
    return slots


def _rehearsals_from(value: Any) -> list[RehearsalRun]:
    runs: list[RehearsalRun] = []
    for item in _as_list(value)[:MAX_REHEARSALS]:
        if not isinstance(item, dict):
            continue
        try:
            chapters = tuple(
                (str(pair[0]), float(pair[1]))
                for pair in _as_list(item.get("chapter_seconds"))
                if isinstance(pair, (list, tuple)) and len(pair) == 2
            )
            runs.append(
                RehearsalRun(
                    finished_at=str(item.get("finished_at", "")),
                    duration_seconds=float(item.get("duration_seconds", 0.0)),
                    word_count=int(item.get("word_count", 0)),
                    chapter_seconds=chapters,
                )
            )
        except (TypeError, ValueError):
            continue
    return runs


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Bring a pre-2.0 payload up to the current schema.

    The 1.x file was ``{"slots": {name: text}, "last_text": "..."}`` with no
    settings and no version marker.
    """
    migrated = dict(data)
    migrated["version"] = SCHEMA_VERSION
    migrated.setdefault("settings", {})
    migrated.setdefault("slots", {})
    migrated.setdefault("last_text", "")
    return migrated


@dataclass(frozen=True)
class LoadResult:
    """Outcome of :func:`load`, including how well it went."""

    data: AppData
    problem: LoadProblem = LoadProblem.NONE
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.problem in (LoadProblem.NONE, LoadProblem.MISSING)


def _read_json(path: Path) -> Any:
    """Parse a JSON file. The caller is responsible for validating the shape."""
    return json.loads(path.read_text(encoding="utf-8"))


def load(path: Path | None = None) -> LoadResult:
    """Load application state, falling back to the backup and then to defaults."""
    target = path or paths.state_file()
    backup = target.with_suffix(target.suffix + ".bak")

    if not target.exists() and not backup.exists():
        legacy = import_legacy()
        if legacy is not None:
            return LoadResult(legacy, LoadProblem.NONE, "migrated from 1.x")
        return LoadResult(AppData(), LoadProblem.MISSING)

    primary_error = ""
    if target.exists():
        try:
            return LoadResult(AppData.from_dict(_read_json(target)))
        except (OSError, ValueError) as exc:
            primary_error = str(exc)

    if backup.exists():
        try:
            return LoadResult(
                AppData.from_dict(_read_json(backup)),
                LoadProblem.RECOVERED_FROM_BACKUP,
                primary_error,
            )
        except (OSError, ValueError) as exc:
            return LoadResult(AppData(), LoadProblem.CORRUPT, f"{primary_error} / {exc}")

    problem = LoadProblem.CORRUPT if primary_error else LoadProblem.UNREADABLE
    return LoadResult(AppData(), problem, primary_error)


def save(data: AppData, path: Path | None = None) -> None:
    """Write state atomically, rotating the previous copy to ``.bak``.

    Raises :class:`OSError` on failure — callers surface that to the user rather
    than pretending the save succeeded.
    """
    target = path or paths.state_file()
    paths.ensure_dir(target.parent)
    payload = json.dumps(data.to_dict(), ensure_ascii=False, indent=2)

    # The temp file lives in the destination directory so os.replace is a true
    # atomic rename; across filesystems it would silently become a copy. It is
    # opened with delete=False because the path has to outlive the handle.
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 — closed via the with-block below
        mode="w",
        encoding="utf-8",
        dir=target.parent,
        prefix=target.name + ".",
        suffix=".tmp",
        delete=False,
    )
    tmp_path = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        if target.exists():
            backup = target.with_suffix(target.suffix + ".bak")
            # A backup that cannot be rotated must never block the real save.
            with contextlib.suppress(OSError):
                os.replace(target, backup)

        os.replace(tmp_path, target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def import_legacy(legacy_path: Path | None = None) -> AppData | None:
    """Read the 1.x ``~/.teleprompter.json`` if it is the only state present."""
    source = legacy_path or paths.LEGACY_SAVE_FILE
    if not source.exists():
        return None
    try:
        return AppData.from_dict(migrate(_read_json(source)))
    except (OSError, ValueError):
        return None
