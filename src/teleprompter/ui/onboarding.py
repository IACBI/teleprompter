"""First-run welcome.

Shown once, on the first launch with an empty script. It answers the three
questions a new user actually has — where do I type, how do I mark up a script,
and how do I get this onto the camera monitor — and then gets out of the way.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..resources import icons
from ..theme.tokens import RADIUS, SPACE, Palette
from .widgets.basic import Separator, label, set_variant

STEPS: tuple[tuple[str, str, str], ...] = (
    (
        "script",
        "Write or import your script",
        "Type into the editor, or import a .txt or .pdf file. Everything is saved "
        "automatically as you work.",
    ),
    (
        "chapter",
        "Mark it up as you go",
        "[PAUSE] stops the scroll · [CHAPTER Title] builds a navigable outline · "
        "[[a note like this]] stays private to you.",
    ),
    (
        "display",
        "Send it to the camera monitor",
        "On the Prompter page, choose the screen and switch on full screen. Turn on "
        "mirroring if your rig reflects the script off glass.",
    ),
)

SAMPLE_SCRIPT = """[CHAPTER Welcome]
This is your script. Replace it with your own words.

The line in the middle of the prompter is where your eye should rest — the
speed control at the bottom of the panel decides how quickly the text arrives
there. [[press play and adjust the speed until it feels right]]

[PAUSE]

[CHAPTER What the tags do]
The scroll just stopped, because the line above was a pause marker. Press play
to carry on.

Chapters appear in the outline beside the editor, and as ticks on the progress
bar. Notes never reach the glass.
"""


class WelcomeDialog(QDialog):
    """A short, one-time introduction."""

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to TelePrompter")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._load_sample = False

        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE.xl, SPACE.xl, SPACE.xl, SPACE.lg)
        column.setSpacing(SPACE.lg)

        heading = label("Welcome to TelePrompter", "heading")
        column.addWidget(heading)
        column.addWidget(
            label(
                "Three things worth knowing before you start.",
                "muted",
                wrap=True,
            )
        )
        column.addWidget(Separator())

        for icon_name, title, body in STEPS:
            column.addWidget(self._step(icon_name, title, body, palette))

        column.addWidget(Separator())

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE.sm)

        sample = QPushButton("Load a sample script")
        sample.setAccessibleName("Load a sample script")
        sample.setToolTip("Fills the editor with a short script that demonstrates the tags")
        sample.clicked.connect(self._accept_with_sample)
        buttons.addWidget(sample)

        buttons.addStretch(1)

        start = QPushButton("Start with an empty script")
        start.setAccessibleName("Start with an empty script")
        start.setDefault(True)
        start.clicked.connect(self.accept)
        set_variant(start, "primary")
        buttons.addWidget(start)

        column.addLayout(buttons)

    def _step(self, icon_name: str, title: str, body: str, palette: Palette) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.lg)

        glyph = QLabel()
        glyph.setPixmap(icons.icon_pixmap(icon_name, palette.accent, 22))
        glyph.setFixedSize(22, 22)
        glyph.setStyleSheet(f"background: {palette.accent_soft}; border-radius: {RADIUS.sm}px;")
        layout.addWidget(glyph, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(SPACE.xxs)
        text.addWidget(label(title, "title"))
        text.addWidget(label(body, "muted", wrap=True))
        layout.addLayout(text, 1)

        return row

    def _accept_with_sample(self) -> None:
        self._load_sample = True
        self.accept()

    @property
    def wants_sample(self) -> bool:
        return self._load_sample
