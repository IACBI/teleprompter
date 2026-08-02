"""Builds the application stylesheet from design tokens.

One sheet is applied to the whole ``QApplication``; no widget sets its own
colours. Variants are selected with Qt dynamic properties, e.g.::

    button.setProperty("variant", "primary")

Changing a property after the widget is shown needs a repolish — use
:func:`repolish`.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .tokens import MIN_HIT_TARGET, RADIUS, SPACE, TYPE, Palette


def repolish(widget: QWidget) -> None:
    """Re-evaluate a widget's style after a dynamic property changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def build_stylesheet(
    palette: Palette, font_family: str, mono_family: str, glyphs: dict[str, str] | None = None
) -> str:
    """Return the full application QSS for ``palette``.

    ``glyphs`` maps a name from :mod:`teleprompter.theme.assets` to a file path.
    When it is missing or incomplete the affected indicators simply keep Qt's
    default appearance.
    """
    p = palette
    glyphs = glyphs or {}

    def image(name: str, fallback: str = "none") -> str:
        path = glyphs.get(name)
        return f"url({path})" if path else fallback

    return f"""
/* ══ Base ══════════════════════════════════════════════════════════════════ */
QWidget {{
    background: transparent;
    color: {p.text};
    font-family: "{font_family}";
    font-size: {TYPE.body}px;
}}

QMainWindow, QDialog, #AppRoot {{
    background: {p.bg};
}}

QToolTip {{
    background: {p.surface_overlay};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: {RADIUS.sm}px;
    padding: {SPACE.xs}px {SPACE.sm}px;
    font-size: {TYPE.small}px;
}}

/* ══ Typography roles ══════════════════════════════════════════════════════ */
QLabel[role="display"] {{
    font-size: {TYPE.display}px;
    font-weight: {TYPE.weight_semibold};
    color: {p.text};
}}
QLabel[role="heading"] {{
    font-size: {TYPE.heading}px;
    font-weight: {TYPE.weight_semibold};
}}
QLabel[role="title"] {{
    font-size: {TYPE.title}px;
    font-weight: {TYPE.weight_semibold};
}}
QLabel[role="section"] {{
    font-size: {TYPE.caption}px;
    font-weight: {TYPE.weight_semibold};
    color: {p.text_subtle};
    letter-spacing: 1px;
}}
QLabel[role="muted"] {{ color: {p.text_muted}; }}
QLabel[role="caption"] {{
    font-size: {TYPE.caption}px;
    color: {p.text_subtle};
}}
QLabel[role="value"] {{
    font-size: {TYPE.small}px;
    font-weight: {TYPE.weight_semibold};
    color: {p.text_muted};
}}
QLabel[role="mono"] {{
    font-family: "{mono_family}";
    font-size: {TYPE.small}px;
    color: {p.text_muted};
}}
QLabel:disabled {{ color: {p.text_disabled}; }}

/* ══ Cards and panels ══════════════════════════════════════════════════════ */
Card, #Card {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: {RADIUS.lg}px;
}}
Card[emphasis="raised"] {{
    background: {p.surface_raised};
}}
#Separator {{
    background: {p.border};
    border: none;
}}

/* ══ Buttons ═══════════════════════════════════════════════════════════════ */
QPushButton {{
    background: {p.surface_raised};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: {RADIUS.md}px;
    padding: {SPACE.sm}px {SPACE.md}px;
    min-height: {MIN_HIT_TARGET - 2 * SPACE.sm}px;
    font-weight: {TYPE.weight_medium};
}}
QPushButton:hover {{
    background: {p.surface_overlay};
    border-color: {p.border_strong};
}}
QPushButton:pressed {{
    background: {p.border};
}}
QPushButton:focus {{
    border: 1px solid {p.accent};
    outline: none;
}}
QPushButton:disabled {{
    background: {p.surface};
    color: {p.text_disabled};
    border-color: {p.border};
}}

QPushButton[variant="primary"] {{
    background: {p.accent};
    color: {p.on_accent};
    border: 1px solid {p.accent};
    font-weight: {TYPE.weight_semibold};
}}
QPushButton[variant="primary"]:hover {{
    background: {p.accent_hover};
    border-color: {p.accent_hover};
}}
QPushButton[variant="primary"]:pressed {{
    background: {p.accent_pressed};
    border-color: {p.accent_pressed};
}}
QPushButton[variant="primary"]:disabled {{
    background: {p.surface_raised};
    color: {p.text_disabled};
    border-color: {p.border};
}}

/* Buttons that set their own geometry in code. A stylesheet min-height wins
   over setFixedSize, which silently squashes icon and touch buttons — this
   rule stands down so the programmatic size stands. */
QPushButton[shape="fixed"] {{
    padding: 0;
    min-width: 0;
    min-height: 0;
}}

QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {p.text_muted};
}}
QPushButton[variant="ghost"]:hover {{
    background: {p.surface_overlay};
    color: {p.text};
}}
QPushButton[variant="ghost"]:pressed {{ background: {p.border}; }}

QPushButton[variant="danger"] {{
    background: transparent;
    color: {p.danger};
    border: 1px solid {p.border_strong};
}}
QPushButton[variant="danger"]:hover {{
    background: {p.danger};
    color: #ffffff;
    border-color: {p.danger};
}}

QPushButton[variant="accentSoft"] {{
    background: {p.accent_soft};
    color: {p.accent};
    border: 1px solid transparent;
}}
QPushButton[variant="accentSoft"]:hover {{ border-color: {p.accent}; }}

/* Colour pickers: the swatch is painted on top, so leave room for it. */
QPushButton[variant="swatch"] {{
    text-align: left;
    padding-left: {SPACE.lg + 22}px;
    font-family: "{mono_family}";
    letter-spacing: 0.5px;
}}

/* ══ Navigation rail ═══════════════════════════════════════════════════════ */
#NavRail {{
    background: {p.surface};
    border-right: 1px solid {p.border};
}}
#NavRail QPushButton {{
    background: transparent;
    border: none;
    border-radius: {RADIUS.md}px;
    color: {p.text_muted};
    padding: {SPACE.sm}px {SPACE.md}px;
    text-align: left;
    font-weight: {TYPE.weight_medium};
}}
#NavRail QPushButton:hover {{
    background: {p.surface_overlay};
    color: {p.text};
}}
#NavRail QPushButton:checked {{
    background: {p.accent_soft};
    color: {p.accent};
    font-weight: {TYPE.weight_semibold};
}}
#NavRail QPushButton:focus {{ border: 1px solid {p.accent}; }}

/* ══ Text entry ════════════════════════════════════════════════════════════ */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background: {p.bg if p.is_dark else p.surface};
    color: {p.text};
    border: 1px solid {p.border};
    border-radius: {RADIUS.md}px;
    padding: {SPACE.sm}px;
    selection-background-color: {p.selection};
    selection-color: {p.on_selection};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {p.border_strong};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {p.accent};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: transparent;
    border: none;
    width: 18px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: {image("chevron-up")};
    width: 12px; height: 12px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: {image("chevron-down")};
    width: 12px; height: 12px;
}}

/* ══ Combo boxes ═══════════════════════════════════════════════════════════ */
QComboBox {{
    background: {p.surface_raised};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: {RADIUS.md}px;
    padding: {SPACE.sm}px {SPACE.md}px;
    min-height: {MIN_HIT_TARGET - 2 * SPACE.sm}px;
}}
QComboBox:hover {{ background: {p.surface_overlay}; }}
QComboBox:focus {{ border-color: {p.accent}; }}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: {image("chevron-down")};
    width: 12px; height: 12px;
    margin-right: {SPACE.sm}px;
}}
QComboBox QAbstractItemView {{
    background: {p.surface_raised};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: {RADIUS.md}px;
    padding: {SPACE.xs}px;
    selection-background-color: {p.accent_soft};
    selection-color: {p.accent};
    outline: none;
}}

/* ══ Sliders ═══════════════════════════════════════════════════════════════ */
QSlider {{ min-height: 24px; }}
QSlider::groove:horizontal {{
    height: 4px;
    background: {p.border};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {p.accent};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {p.text if p.is_dark else p.surface};
    border: 2px solid {p.accent};
    width: 12px;
    height: 12px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: {p.accent};
    border-color: {p.accent_hover};
    width: 14px; height: 14px;
    margin: -7px -1px;
    border-radius: 9px;
}}
QSlider::handle:horizontal:pressed {{ background: {p.accent_pressed}; }}
QSlider:focus::handle:horizontal {{ border-color: {p.accent_hover}; }}
QSlider::groove:horizontal:disabled {{ background: {p.surface_raised}; }}
QSlider::sub-page:horizontal:disabled {{ background: {p.text_disabled}; }}
QSlider::handle:horizontal:disabled {{
    background: {p.surface_raised};
    border-color: {p.text_disabled};
}}

/* ══ Progress ══════════════════════════════════════════════════════════════ */
QProgressBar {{
    background: {p.border};
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {p.accent};
    border-radius: 3px;
}}

/* ══ Check boxes and radios ════════════════════════════════════════════════ */
QCheckBox, QRadioButton {{
    spacing: {SPACE.sm}px;
    color: {p.text};
    padding: {SPACE.xs}px 0;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {p.border_strong};
    background: {p.surface_raised};
}}
QCheckBox::indicator {{ border-radius: {RADIUS.sm}px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {p.accent};
}}
QCheckBox::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
    image: {image("check")};
}}
QCheckBox::indicator:indeterminate {{
    background: {p.accent};
    border-color: {p.accent};
    image: {image("dash")};
}}
QRadioButton::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {p.surface};
    border-color: {p.border};
}}

/* ══ Lists ═════════════════════════════════════════════════════════════════ */
QListWidget, QListView, QTreeView, QTableView {{
    background: {p.bg if p.is_dark else p.surface};
    border: 1px solid {p.border};
    border-radius: {RADIUS.md}px;
    outline: none;
    padding: {SPACE.xs}px;
}}
QListWidget::item, QListView::item {{
    padding: {SPACE.sm}px {SPACE.sm}px;
    border-radius: {RADIUS.sm}px;
    color: {p.text_muted};
}}
QListWidget::item:hover, QListView::item:hover {{
    background: {p.surface_overlay};
    color: {p.text};
}}
QListWidget::item:selected, QListView::item:selected {{
    background: {p.accent_soft};
    color: {p.accent};
}}

/* ══ Scroll bars ═══════════════════════════════════════════════════════════ */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p.border_strong};
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.text_subtle}; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {p.border_strong};
    border-radius: 5px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{ background: {p.text_subtle}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0; width: 0; background: none; border: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

/* ══ Scroll areas ══════════════════════════════════════════════════════════ */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ══ Menus ═════════════════════════════════════════════════════════════════ */
QMenu {{
    background: {p.surface_raised};
    border: 1px solid {p.border_strong};
    border-radius: {RADIUS.md}px;
    padding: {SPACE.xs}px;
}}
QMenu::item {{
    padding: {SPACE.sm}px {SPACE.lg}px;
    border-radius: {RADIUS.sm}px;
    color: {p.text_muted};
}}
QMenu::item:selected {{
    background: {p.accent_soft};
    color: {p.accent};
}}
QMenu::separator {{
    height: 1px;
    background: {p.border};
    margin: {SPACE.xs}px {SPACE.sm}px;
}}

/* ══ Splitters ═════════════════════════════════════════════════════════════ */
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: {SPACE.sm}px; }}
QSplitter::handle:vertical {{ height: {SPACE.sm}px; }}
QSplitter::handle:hover {{ background: {p.accent_soft}; }}

/* ══ Group boxes (dialogs only — pages use Card) ═══════════════════════════ */
QGroupBox {{
    border: 1px solid {p.border};
    border-radius: {RADIUS.md}px;
    margin-top: {SPACE.md}px;
    padding-top: {SPACE.md}px;
    font-weight: {TYPE.weight_semibold};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {SPACE.md}px;
    padding: 0 {SPACE.xs}px;
    color: {p.text_subtle};
}}

/* ══ Dialogs ═══════════════════════════════════════════════════════════════ */
QMessageBox, QInputDialog, QColorDialog, QFileDialog {{
    background: {p.bg};
}}
QMessageBox QLabel, QInputDialog QLabel {{ color: {p.text}; }}
"""
