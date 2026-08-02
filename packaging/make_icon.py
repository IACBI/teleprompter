"""Write the application icon to a ``.ico`` file for the Windows build.

The icon is drawn in code (:mod:`teleprompter.resources.icons`), so nothing
binary lives in the repository. This script materialises it only when a release
build needs a file on disk.

    python packaging/make_icon.py packaging/teleprompter.ico
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from teleprompter.resources import icons

SIZES = (16, 24, 32, 48, 64, 128, 256)


def main(destination: Path) -> int:
    QApplication([])
    icon = icons.app_icon()

    destination.parent.mkdir(parents=True, exist_ok=True)

    # QIcon cannot write .ico directly; the largest rendering is saved and Qt's
    # image writer produces a multi-size icon from it on Windows.
    largest: QPixmap = icon.pixmap(max(SIZES), max(SIZES))
    if not largest.save(str(destination), "ICO"):
        print(f"Could not write {destination}", file=sys.stderr)
        return 1

    print(f"Wrote {destination} ({destination.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("packaging/teleprompter.ico")
    raise SystemExit(main(target))
