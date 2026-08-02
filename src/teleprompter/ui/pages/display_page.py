"""How the script looks on the glass."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QComboBox, QFontComboBox, QWidget

from ...core.settings import ALIGNMENTS, LIMITS, PROMPTER_THEMES, Settings
from ...theme.tokens import Palette
from ..widgets.basic import Card
from ..widgets.controls import (
    ColorSwatchButton,
    LabeledSlider,
    SegmentedControl,
    ToggleSwitch,
)
from .base import Page


class DisplayPage(Page):
    """Typography, colour and reading aids for the prompter window."""

    TITLE = "Display"
    ICON = "display"

    def __init__(self, state, playback, parent: QWidget | None = None) -> None:
        super().__init__(state, playback, parent)

        self._toggles: dict[str, ToggleSwitch] = {}
        self._segments: list[SegmentedControl] = []

        self.content.addWidget(self._typography_card())
        self.content.addWidget(self._appearance_card())
        self.content.addWidget(self._reading_card())
        self.finish()

        self.sync(state.settings)

    # ── Cards ─────────────────────────────────────────────────────────────────
    def _typography_card(self) -> Card:
        card = Card("Typography", "Bigger and looser is easier to read at distance.")

        self.font_box = QFontComboBox()
        self.font_box.setEditable(False)
        self.font_box.currentFontChanged.connect(lambda font: self._set(font_family=font.family()))
        card.add_row("Typeface", self.font_box)

        self.font_size = LabeledSlider(LIMITS["font_size"], suffix=" pt", decimals=0)
        self.font_size.valueChanged.connect(lambda v: self._set(font_size=int(v)))
        card.add_row("Size", self.font_size)

        self.line_spacing = LabeledSlider(LIMITS["line_spacing"], suffix="×", decimals=2)
        self.line_spacing.valueChanged.connect(lambda v: self._set(line_spacing=v))
        card.add_row("Line spacing", self.line_spacing)

        self.alignment = SegmentedControl(["Left", "Centre", "Right"])
        self.alignment.currentChanged.connect(lambda index: self._set(alignment=ALIGNMENTS[index]))
        self._segments.append(self.alignment)
        card.add_row("Alignment", self.alignment)

        self.margins = LabeledSlider(
            LIMITS["margin_ratio"], decimals=0, formatter=lambda v: f"{v * 100:.0f} %"
        )
        self.margins.valueChanged.connect(lambda v: self._set(margin_ratio=v))
        card.add_row("Side margins", self.margins)
        return card

    def _appearance_card(self) -> Card:
        card = Card("Appearance", "Presets set all three at once; adjust from there.")

        self.theme_box = QComboBox()
        self.theme_box.addItems(list(PROMPTER_THEMES))
        self.theme_box.currentTextChanged.connect(self._on_theme)
        card.add_row("Preset", self.theme_box)

        self.text_color = ColorSwatchButton("Text colour")
        self.text_color.colorPicked.connect(lambda value: self._set(text_color=value))
        card.add_row("Text colour", self.text_color)

        self.bg_color = ColorSwatchButton("Background colour")
        self.bg_color.colorPicked.connect(lambda value: self._set(bg_color=value))
        card.add_row("Background", self.bg_color)

        self.opacity = LabeledSlider(
            LIMITS["bg_opacity"], decimals=0, formatter=lambda v: f"{v * 100:.0f} %"
        )
        self.opacity.valueChanged.connect(lambda v: self._set(bg_opacity=v))
        card.add_row(
            "Background opacity",
            self.opacity,
        )
        return card

    def _reading_card(self) -> Card:
        card = Card("Reading aids", "Where the eye rests, and what helps it stay there.")

        self.focus = LabeledSlider(
            LIMITS["focus_ratio"], decimals=0, formatter=lambda v: f"{v * 100:.0f} %"
        )
        self.focus.valueChanged.connect(lambda v: self._set(focus_ratio=v))
        card.add_row(
            "Focus line position", self.focus, "Measured from the top of the prompter window."
        )

        for key, title, hint in (
            (
                "word_highlight",
                "Highlight current word",
                "Sweeps a warm tint across the line as it is read.",
            ),
            (
                "mirror_x",
                "Mirror horizontally",
                "For beam-splitter glass mounted in front of the lens.",
            ),
            (
                "mirror_y",
                "Mirror vertically",
                "For rigs that reflect the screen off an overhead mirror.",
            ),
            ("show_hud", "Show chapter and progress readout", ""),
            (
                "touch_controls",
                "Show large on-screen buttons",
                "Useful on a tablet or a touchscreen prompter.",
            ),
        ):
            toggle = ToggleSwitch()
            toggle.toggled.connect(lambda checked, name=key: self._set(**{name: checked}))
            self._toggles[key] = toggle
            card.add_row(title, toggle, hint, expand=False)

        return card

    # ── Wiring ────────────────────────────────────────────────────────────────
    def _set(self, **changes) -> None:
        if not self.syncing:
            self.state.update_settings(**changes)

    def _on_theme(self, name: str) -> None:
        if self.syncing:
            return
        self.state.apply_prompter_theme(name)

    def on_palette(self, palette: Palette, ui_font: str, mono_font: str) -> None:
        for toggle in self._toggles.values():
            toggle.apply_palette(palette)
        for segment in self._segments:
            segment.apply_palette(palette)
        self.text_color.apply_palette(palette)
        self.bg_color.apply_palette(palette)

    def sync(self, settings: Settings) -> None:
        with self.guard():
            self.font_box.setCurrentFont(QFont(settings.font_family))
            self.font_size.set_value(settings.font_size)
            self.line_spacing.set_value(settings.line_spacing)
            self.alignment.set_current_index(ALIGNMENTS.index(settings.alignment), animate=False)
            self.margins.set_value(settings.margin_ratio)

            index = self.theme_box.findText(settings.theme)
            self.theme_box.setCurrentIndex(index if index >= 0 else 0)
            self.text_color.set_color(settings.text_color)
            self.bg_color.set_color(settings.bg_color)
            self.opacity.set_value(settings.bg_opacity)

            self.focus.set_value(settings.focus_ratio)
            for key, toggle in self._toggles.items():
                toggle.setChecked(getattr(settings, key))
