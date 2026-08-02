"""Where the prompter window lives, and how it starts moving.

Multi-screen placement belongs here: in a studio the prompter goes to the
display bolted to the camera, and it needs to get there in one click.
"""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QSpinBox, QWidget

from ...core.settings import LIMITS, SPEED_MODES, Settings
from ...theme.tokens import SPACE, Palette
from ..widgets.basic import Card, IconButton, set_variant
from ..widgets.controls import LabeledSlider, SegmentedControl, ToggleSwitch
from .base import Page


class PrompterPage(Page):
    """Display placement, window visibility and how playback ramps up."""

    TITLE = "Prompter"
    ICON = "playback"

    def __init__(self, state, playback, prompter, notes, parent: QWidget | None = None) -> None:
        super().__init__(state, playback, parent)
        self._prompter = prompter
        self._notes = notes
        self._toggles: dict[str, ToggleSwitch] = {}
        self._segments: list[SegmentedControl] = []
        self._icon_buttons: list[IconButton] = []

        self.content.addWidget(self._window_card())
        self.content.addWidget(self._start_card())
        self.finish()

        QGuiApplication.instance().screenAdded.connect(lambda _s: self._refresh_screens())
        QGuiApplication.instance().screenRemoved.connect(lambda _s: self._refresh_screens())

        self.sync(state.settings)

    # ── Cards ─────────────────────────────────────────────────────────────────
    def _window_card(self) -> Card:
        card = Card("Display window", "Send the prompter to the screen the talent reads from.")

        self.screen_box = QComboBox()
        self.screen_box.setAccessibleName("Prompter screen")
        self.screen_box.setToolTip("Choose which connected display shows the prompter")
        self.screen_box.currentIndexChanged.connect(self._on_screen_chosen)
        card.add_row("Screen", self.screen_box)

        self.fullscreen = ToggleSwitch()
        self.fullscreen.toggled.connect(self._on_fullscreen)
        self._toggles["prompter_fullscreen"] = self.fullscreen
        card.add_row(
            "Full screen",
            self.fullscreen,
            "Press F11 on the prompter window to leave full screen.",
            expand=False,
        )

        row = QHBoxLayout()
        row.setSpacing(SPACE.sm)
        for text, tooltip, handler, variant in (
            (
                "Show prompter",
                "Bring the prompter window to the front",
                self._show_prompter,
                "primary",
            ),
            ("Hide", "Hide the prompter window", self._hide_prompter, ""),
            ("Presenter notes", "Open the private notes window", self._show_notes, ""),
        ):
            button = QPushButton(text)
            button.setToolTip(tooltip)
            button.setAccessibleName(text)
            button.clicked.connect(handler)
            if variant:
                set_variant(button, variant)
            row.addWidget(button)
        card.add_layout(row)
        return card

    def _start_card(self) -> Card:
        card = Card("Starting and stopping", "How the scroll behaves when you press play.")

        self.countdown = QSpinBox()
        self.countdown.setRange(
            int(LIMITS["countdown_secs"].minimum), int(LIMITS["countdown_secs"].maximum)
        )
        self.countdown.setSuffix(" s")
        self.countdown.setSpecialValueText("None")
        self.countdown.setAccessibleName("Countdown before playback")
        self.countdown.valueChanged.connect(lambda v: self._set(countdown_secs=v))
        card.add_row(
            "Countdown", self.countdown, "A moment to draw breath before the script starts moving."
        )

        self.speed_mode = SegmentedControl(["Smooth", "Instant"])
        self.speed_mode.currentChanged.connect(
            lambda index: self._set(speed_mode=SPEED_MODES[index])
        )
        self._segments.append(self.speed_mode)
        card.add_row(
            "Speed changes",
            self.speed_mode,
            "Smooth eases into the new speed; instant applies it on the next frame.",
        )

        self.ramp = LabeledSlider(LIMITS["ramp_tau"], suffix=" s", decimals=2)
        self.ramp.valueChanged.connect(lambda v: self._set(ramp_tau=v))
        card.add_row("Ease duration", self.ramp)

        return card

    # ── Screens ───────────────────────────────────────────────────────────────
    def _refresh_screens(self) -> None:
        screens = QGuiApplication.screens()
        with self.guard():
            self.screen_box.clear()
            for screen in screens:
                geometry = screen.geometry()
                primary = " · primary" if screen == QGuiApplication.primaryScreen() else ""
                self.screen_box.addItem(
                    f"{screen.name()} — {geometry.width()}×{geometry.height()}{primary}",
                    screen.name(),
                )
            wanted = self.state.settings.prompter_screen
            index = self.screen_box.findData(wanted) if wanted else -1
            self.screen_box.setCurrentIndex(index if index >= 0 else 0)
        self.screen_box.setEnabled(len(screens) > 0)

    def _selected_screen(self) -> QScreen | None:
        name = self.screen_box.currentData()
        for screen in QGuiApplication.screens():
            if screen.name() == name:
                return screen
        return QGuiApplication.primaryScreen()

    def _on_screen_chosen(self, _index: int) -> None:
        if self.syncing:
            return
        screen = self._selected_screen()
        if screen is None:
            return
        self.state.update_settings(prompter_screen=screen.name())
        self._prompter.move_to_screen(screen, self.state.settings.prompter_fullscreen)
        self.notify.emit(f"Prompter moved to {screen.name()}.", "info")

    def _on_fullscreen(self, enabled: bool) -> None:
        if self.syncing:
            return
        self.state.update_settings(prompter_fullscreen=enabled)
        screen = self._selected_screen()
        if screen is not None:
            self._prompter.move_to_screen(screen, enabled)

    def _show_prompter(self) -> None:
        self._prompter.show()
        self._prompter.raise_()
        self._prompter.activateWindow()

    def _hide_prompter(self) -> None:
        self._prompter.hide()
        self.notify.emit("Prompter hidden. Use Show prompter to bring it back.", "info")

    def _show_notes(self) -> None:
        self._notes.show()
        self._notes.raise_()
        self._notes.activateWindow()

    # ── Wiring ────────────────────────────────────────────────────────────────
    def _set(self, **changes) -> None:
        if not self.syncing:
            self.state.update_settings(**changes)

    def on_palette(self, palette: Palette, ui_font: str, mono_font: str) -> None:
        for toggle in self._toggles.values():
            toggle.apply_palette(palette)
        for segment in self._segments:
            segment.apply_palette(palette)
        for button in self._icon_buttons:
            button.apply_palette(palette)

    def sync(self, settings: Settings) -> None:
        self._refresh_screens()
        with self.guard():
            self.countdown.setValue(settings.countdown_secs)
            self.speed_mode.set_current_index(SPEED_MODES.index(settings.speed_mode), animate=False)
            self.ramp.set_value(settings.ramp_tau)
            self.fullscreen.setChecked(settings.prompter_fullscreen)
        self.ramp.setEnabled(settings.speed_mode == "smooth")
