"""The design system.

Every colour, radius, spacing step and duration used anywhere in the interface
is defined in :mod:`~teleprompter.theme.tokens` and consumed from there. No
widget carries a hard-coded hex value, which is what lets the whole application
— not just the prompter canvas — follow the selected theme.
"""

from .assets import ensure_glyphs
from .stylesheet import build_stylesheet
from .tokens import DARK, LIGHT, MOTION, RADIUS, SPACE, TYPE, Palette, palette_for

__all__ = [
    "DARK",
    "LIGHT",
    "MOTION",
    "RADIUS",
    "SPACE",
    "TYPE",
    "Palette",
    "build_stylesheet",
    "ensure_glyphs",
    "palette_for",
]
