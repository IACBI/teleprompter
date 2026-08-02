"""Stylesheet glyphs.

Qt stylesheets can only point at an image file — they cannot take inline SVG or
a data URI. The usual workaround is the CSS border triangle, which renders as a
blurry lump at fractional scale factors. Instead the few glyphs the sheet needs
(the combo chevron, the spin arrows, the check mark) are written out as tiny SVG
files, tinted for the active palette, and referenced by path.

They are regenerated whenever the theme changes and live in the app cache
directory, so nothing binary ships with the package.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..storage import paths
from .tokens import Palette

log = logging.getLogger(__name__)

_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
    'width="{size}" height="{size}">'
    '<path d="{path}" fill="none" stroke="{colour}" stroke-width="{width}" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)

#: glyph name → (viewBox size, path, stroke width, which palette colour)
_GLYPHS: dict[str, tuple[int, str, float, str]] = {
    "chevron-down": (12, "M2.5 4.5 L6 8 L9.5 4.5", 1.6, "text_muted"),
    "chevron-up": (12, "M2.5 7.5 L6 4 L9.5 7.5", 1.6, "text_muted"),
    "check": (12, "M2.5 6.3 L5 8.8 L9.5 3.4", 1.9, "on_accent"),
    "dash": (12, "M3 6 L9 6", 1.9, "on_accent"),
}


def glyph_dir() -> Path:
    return paths.config_dir() / "glyphs"


def ensure_glyphs(palette: Palette) -> dict[str, str]:
    """Write the glyph set for ``palette`` and return name → stylesheet path.

    Returns an empty mapping if the files cannot be written; the stylesheet then
    falls back to Qt's built-in indicators rather than showing nothing.
    """
    try:
        directory = paths.ensure_dir(glyph_dir())
    except OSError:
        log.warning("Stylesheet glyphs could not be written", exc_info=True)
        return {}

    result: dict[str, str] = {}
    for name, (size, path_data, width, colour_attr) in _GLYPHS.items():
        markup = _TEMPLATE.format(
            size=size,
            path=path_data,
            colour=getattr(palette, colour_attr),
            width=width,
        )
        target = directory / f"{name}-{palette.name}.svg"
        try:
            if not target.exists() or target.read_text(encoding="utf-8") != markup:
                target.write_text(markup, encoding="utf-8")
        except OSError:
            log.warning("Could not write glyph %s", target, exc_info=True)
            continue
        # Qt stylesheets want forward slashes on every platform.
        result[name] = target.as_posix()

    return result
