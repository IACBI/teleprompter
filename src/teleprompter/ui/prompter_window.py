"""The prompter display.

A frameless, translucent, always-on-top window that draws the script itself
rather than hosting a text widget. That is what makes the reading experience
controllable: the focus band, the distance fade, the per-word sweep and the
mirror transform are all one paint pass over the handful of lines that are
actually visible.

Cost per frame is proportional to the number of visible lines, never to the
length of the script. Wrapping happens only when the text, width or font
changes, and even then it is coalesced so dragging a slider stays smooth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QScreen,
    QStaticText,
)
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizeGrip, QWidget

from ..core import timing
from ..core.layout import EMPTY_LAYOUT, Layout, build_layout, line_origin_x
from ..core.script import BlockKind
from ..core.transport import PlayState
from ..resources import icons
from ..state import AppState, PlaybackController
from ..theme.tokens import MIN_TOUCH_TARGET, MOTION, RADIUS, SPACE, TYPE, Palette

log = logging.getLogger(__name__)

#: Corner radius of the overlay itself.
WINDOW_RADIUS = 18
#: Height of the strip at the top that acts as the window's drag handle.
DRAG_STRIP = 44
#: Re-wrapping is deferred by this long so a slider drag or a window resize
#: coalesces into a single layout pass.
RELAYOUT_DELAY_MS = 45

#: Settings that change how text is laid out. Anything else — colours, opacity,
#: mirroring — only needs a repaint.
_LAYOUT_SETTINGS = ("font_family", "font_size", "line_spacing", "margin_ratio")


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


#: Normalised distance → opacity, smoothstepped so lines melt away instead of
#: stepping. Index 0 is the focus line, 255 is the edge of the fade span.
_FADE_LUT: tuple[float, ...] = tuple(1.0 - _smoothstep(i / 255.0) for i in range(256))


@dataclass
class _FontCache:
    font: QFont
    metrics: QFontMetricsF
    line_height: int
    ascent: float
    space_width: float
    key: tuple


class PrompterWindow(QWidget):
    """The audience-facing (or mirror-glass-facing) display."""

    closed = Signal()

    def __init__(
        self, state: AppState, playback: PlaybackController, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._playback = playback
        self._palette: Palette | None = None

        self.setWindowTitle("TelePrompter — Display")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(480, 320)
        self.resize(960, 600)
        self.setAccessibleName("Prompter display")

        # ── Caches ────────────────────────────────────────────────────────────
        self._font_cache: _FontCache | None = None
        self._layout: Layout = EMPTY_LAYOUT
        self._layout_key: tuple = ()
        self._static: dict[int, QStaticText] = {}
        self._colors: dict[str, QColor] = {}
        self._chrome_cache: QPixmap | None = None
        self._chrome_key: tuple = ()
        self._last_chapter = ""
        self._last_focus_line = -1
        self._notes_target = None
        self._applied_settings = None

        # ── Interaction ───────────────────────────────────────────────────────
        self._drag_origin: QPoint | None = None
        self._hover_drag_strip = False

        # ── Countdown animation ───────────────────────────────────────────────
        self._countdown_scale = 1.0
        self._countdown_anim = QPropertyAnimation(self, b"countdownScale", self)
        self._countdown_anim.setDuration(MOTION.slow)
        self._countdown_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # ── Deferred relayout ─────────────────────────────────────────────────
        self._relayout = QTimer(self)
        self._relayout.setSingleShot(True)
        self._relayout.setInterval(RELAYOUT_DELAY_MS)
        self._relayout.timeout.connect(self._rebuild_layout)

        self._build_touch_bar()

        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(20, 20)
        self._grip.setToolTip("Drag to resize the prompter")
        self._grip.setStyleSheet("background: transparent;")

        # ── Wiring ────────────────────────────────────────────────────────────
        state.settingsChanged.connect(self._on_settings_changed)
        state.scriptChanged.connect(self._on_script_changed)
        playback.repaintRequested.connect(self.update)
        playback.stateChanged.connect(self._on_play_state)
        playback.countdownChanged.connect(self._on_countdown)
        playback.positionChanged.connect(self._on_position_changed)

        self._apply_settings(state.settings)

    # ══ Theme ═════════════════════════════════════════════════════════════════
    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        for button in self._touch_buttons.values():
            self._style_touch_button(button)
        self._sync_touch_icons()
        self.update()

    def attach_notes(self, notes_window) -> None:
        """The notes window is fed from here, since this is where lines are resolved."""
        self._notes_target = notes_window
        self._push_notes()

    # ══ Settings ══════════════════════════════════════════════════════════════
    def _on_settings_changed(self, settings) -> None:
        previous, self._applied_settings = self._applied_settings, settings
        needs_relayout = previous is None or any(
            getattr(previous, name) != getattr(settings, name) for name in _LAYOUT_SETTINGS
        )
        self._apply_settings(settings, relayout=needs_relayout)

    def _apply_settings(self, settings, *, relayout: bool = True) -> None:
        self._applied_settings = settings
        self._rebuild_colors(settings)
        self._touch_bar.setVisible(settings.touch_controls)
        if settings.touch_controls:
            self._position_touch_bar()
        if relayout:
            self._invalidate_font()
        self.update()

    def _rebuild_colors(self, settings) -> None:
        background = QColor(settings.bg_color)
        background.setAlphaF(settings.bg_opacity)
        text = QColor(settings.text_color)

        accent = QColor(self._palette.accent) if self._palette else QColor("#ffb020")
        highlight = QColor(accent)
        highlight.setHsvF(accent.hueF(), min(1.0, accent.saturationF() * 0.8), 1.0)

        # The hairline edge has to read against whatever is behind the window,
        # so it follows the panel colour rather than a fixed white.
        chrome = QColor(255, 255, 255, 28) if _is_dark(background) else QColor(0, 0, 0, 34)

        self._colors = {
            "bg": background,
            "text": text,
            "highlight": highlight,
            "accent": accent,
            "chrome": chrome,
            # Light text over an unknown desktop needs a dark shadow; dark text
            # needs a light halo. Both keep the script readable at low opacity.
            "readability": QColor(0, 0, 0) if not _is_dark(text) else QColor(255, 255, 255),
        }

    # ══ Font and layout ═══════════════════════════════════════════════════════
    def _invalidate_font(self) -> None:
        self._font_cache = None
        self._layout_key = ()
        self._static.clear()
        self._relayout.start()

    def _ensure_font(self) -> _FontCache:
        settings = self._state.settings
        key = (settings.font_family, settings.font_size, settings.line_spacing)
        cache = self._font_cache
        if cache is not None and cache.key == key:
            return cache

        font = QFont(settings.font_family)
        font.setPointSizeF(float(settings.font_size))
        font.setWeight(QFont.Weight.DemiBold)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)

        metrics = QFontMetricsF(font)
        cache = _FontCache(
            font=font,
            metrics=metrics,
            line_height=max(1, round(metrics.lineSpacing() * settings.line_spacing)),
            ascent=metrics.ascent(),
            space_width=metrics.horizontalAdvance(" "),
            key=key,
        )
        self._font_cache = cache
        self._static.clear()
        return cache

    def _margin(self) -> int:
        return max(SPACE.lg, int(self.width() * self._state.settings.margin_ratio))

    def _rebuild_layout(self) -> None:
        font = self._ensure_font()
        script = self._state.script
        margin = self._margin()
        max_width = max(1, self.width() - 2 * margin)
        key = (id(script), script.raw, max_width, font.key)

        if key == self._layout_key:
            return

        self._layout = build_layout(
            script,
            max_width,
            lambda text: round(font.metrics.horizontalAdvance(text)),
            round(font.space_width),
        )
        self._layout_key = key
        self._static.clear()

        self._playback.set_metrics(
            float(len(self._layout) * font.line_height),
            font.line_height,
            self._layout.pause_lines,
        )
        self._push_notes()
        self.update()

    def _ensure_layout(self) -> None:
        if not self._layout_key:
            self._rebuild_layout()

    def _on_script_changed(self, _script) -> None:
        self._layout_key = ()
        self._last_chapter = ""
        self._relayout.start()

    def _push_notes(self) -> None:
        if self._notes_target is not None:
            self._notes_target.set_notes(self._layout.notes_by_line, self._layout.lines)

    # ══ Playback reactions ════════════════════════════════════════════════════
    def _on_play_state(self, state: PlayState) -> None:
        self._sync_touch_icons()
        self.update()

    def _on_countdown(self, value) -> None:
        if value is None:
            return
        self._countdown_anim.stop()
        self._countdown_anim.setStartValue(0.55)
        self._countdown_anim.setEndValue(1.0)
        self._countdown_anim.start()

    def get_countdown_scale(self) -> float:
        return self._countdown_scale

    def set_countdown_scale(self, value: float) -> None:
        self._countdown_scale = value
        self.update()

    countdownScale = Property(float, get_countdown_scale, set_countdown_scale)

    # ══ Painting ══════════════════════════════════════════════════════════════
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        width, height = self.width(), self.height()
        body = QRectF(0.5, 0.5, width - 1, height - 1)

        self._paint_chrome(painter, body)

        countdown = self._playback.countdown_value
        if countdown is not None:
            self._paint_countdown(painter, countdown)
            self._paint_edge_grips(painter)
            return

        self._ensure_layout()
        if self._state.script.is_empty:
            self._paint_empty_state(painter)
            self._paint_edge_grips(painter)
            return

        self._paint_script(painter)
        self._paint_hud(painter)
        self._paint_edge_grips(painter)

    def _paint_chrome(self, painter: QPainter, body: QRectF) -> None:
        """Rounded translucent panel with a soft outer halo.

        The panel never changes between frames, so it is rendered once into a
        pixmap and blitted afterwards — four antialiased rounded-rect passes per
        frame is a lot to spend on something static.
        """
        key = (
            self.width(),
            self.height(),
            self._colors["bg"].rgba(),
            self._colors["chrome"].rgba(),
        )
        if key != self._chrome_key or self._chrome_cache is None:
            self._chrome_cache = self._render_chrome(body)
            self._chrome_key = key
        painter.drawPixmap(0, 0, self._chrome_cache)

    def _render_chrome(self, body: QRectF) -> QPixmap:
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(int(self.width() * ratio), int(self.height() * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(body, WINDOW_RADIUS, WINDOW_RADIUS)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._colors["bg"])
        painter.drawPath(path)

        # Three decreasing strokes read as a soft edge without a blur pass.
        base = self._colors["chrome"]
        for index, inset in enumerate((0.0, 1.5, 3.0)):
            colour = QColor(base)
            colour.setAlpha(max(0, base.alpha() - index * 9))
            painter.setPen(QPen(colour, 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(
                body.adjusted(inset, inset, -inset, -inset),
                WINDOW_RADIUS - inset,
                WINDOW_RADIUS - inset,
            )
        painter.end()
        return pixmap

    def _paint_script(self, painter: QPainter) -> None:
        settings = self._state.settings
        font = self._ensure_font()
        lines = self._layout.lines
        line_height = font.line_height
        width, height = self.width(), self.height()
        focus_y = int(height * settings.focus_ratio)
        margin = self._margin()

        self._paint_focus_band(painter, focus_y, line_height, width)

        scroll_y = self._playback.scroll_y
        start_y = focus_y - scroll_y
        fade_span = max(line_height * 2.2, height * 0.46)

        first = max(0, int((-start_y) // line_height) - 1)
        last = min(len(lines), first + int(height // line_height) + 3)

        focus_index = int(scroll_y // line_height)
        focus_fraction = (scroll_y / line_height) - focus_index

        painter.save()
        if settings.mirror_x:
            painter.translate(width, 0)
            painter.scale(-1, 1)
        if settings.mirror_y:
            painter.translate(0, height)
            painter.scale(1, -1)

        painter.setFont(font.font)
        text_colour = self._colors["text"]
        highlight = self._colors["highlight"]
        accent = self._colors["accent"]
        readability = self._colors["readability"]

        for index in range(first, last):
            line = lines[index]
            top = start_y + index * line_height
            distance = abs(top + font.ascent - focus_y)
            opacity = _FADE_LUT[min(255, int(255 * distance / fade_span))]
            if opacity <= 0.02:
                continue

            if line.kind is BlockKind.BLANK:
                continue
            if line.kind is BlockKind.PAUSE:
                self._paint_pause_chip(painter, top, line_height, width, margin, opacity)
                continue

            origin = line_origin_x(line.width, settings.alignment, width, margin)

            if line.kind is BlockKind.CHAPTER:
                self._paint_chapter_line(painter, line, top, origin, opacity, accent, font)
                continue

            self._paint_readability_layer(painter, line, index, origin, top, opacity, readability)

            if settings.word_highlight and index == focus_index and line.words:
                self._paint_words(
                    painter,
                    line,
                    origin,
                    top,
                    font,
                    opacity,
                    focus_fraction,
                    text_colour,
                    highlight,
                )
            else:
                colour = QColor(text_colour)
                colour.setAlphaF(opacity * (text_colour.alphaF() or 1.0))
                painter.setPen(colour)
                painter.drawStaticText(
                    QPoint(int(origin), int(top)), self._static_text(index, line.text)
                )

        painter.restore()
        self._paint_guides(painter, focus_y, line_height, width)

    def _static_text(self, index: int, text: str) -> QStaticText:
        cached = self._static.get(index)
        if cached is None:
            cached = QStaticText(text)
            cached.setTextFormat(Qt.TextFormat.PlainText)
            cached.setPerformanceHint(QStaticText.PerformanceHint.AggressiveCaching)
            if len(self._static) > 512:
                self._static.clear()
            self._static[index] = cached
        return cached

    def _paint_readability_layer(
        self,
        painter: QPainter,
        line,
        index: int,
        origin: int,
        top: float,
        opacity: float,
        colour: QColor,
    ) -> None:
        """Two soft offsets keep the script legible over an unknown backdrop.

        Light text gets a dark shadow, dark text a light halo — a real Gaussian
        blur per frame would cost far more than it is worth here. Lines that are
        already fading out skip the layer entirely, and then the second pass,
        because nobody can see a shadow under 30% opaque text.
        """
        if opacity < 0.28:
            return
        passes = (((1, 1), 0.38), ((2, 3), 0.20)) if opacity > 0.6 else (((1, 1), 0.34),)

        static = self._static_text(index, line.text)
        tint = QColor(colour)
        for offset, strength in passes:
            tint.setAlphaF(opacity * strength)
            painter.setPen(tint)
            painter.drawStaticText(QPoint(int(origin) + offset[0], int(top) + offset[1]), static)

    def _paint_words(
        self,
        painter: QPainter,
        line,
        origin: int,
        top: float,
        font: _FontCache,
        opacity: float,
        fraction: float,
        text_colour: QColor,
        highlight: QColor,
    ) -> None:
        """Draw the focus line word by word with a sweeping highlight."""
        count = len(line.words)
        position = fraction * count
        current = min(count - 1, int(position))
        within = position - current
        baseline = top + font.ascent

        pairs = zip(line.words, line.word_offsets, strict=True)
        for word_index, (word, offset) in enumerate(pairs):
            if word_index == current:
                weight = 1.0
            elif word_index == current + 1:
                weight = _smoothstep(within) * 0.55
            else:
                weight = 0.0

            colour = _mix(text_colour, highlight, weight)
            colour.setAlphaF(opacity)

            x = origin + offset
            if weight > 0.5:
                glow = QColor(highlight)
                glow.setAlphaF(opacity * 0.28)
                painter.setPen(glow)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    painter.drawText(QPoint(int(x + dx), int(baseline + dy)), word)

            painter.setPen(colour)
            painter.drawText(QPoint(int(x), int(baseline)), word)

    def _paint_chapter_line(
        self,
        painter: QPainter,
        line,
        top: float,
        origin: int,
        opacity: float,
        accent: QColor,
        font: _FontCache,
    ) -> None:
        colour = QColor(accent)
        colour.setAlphaF(opacity)
        painter.setPen(colour)
        painter.drawText(QPoint(int(origin), int(top + font.ascent)), line.text)

    def _paint_pause_chip(
        self,
        painter: QPainter,
        top: float,
        line_height: int,
        width: int,
        margin: int,
        opacity: float,
    ) -> None:
        accent = QColor(self._colors["accent"])
        middle = top + line_height / 2

        line_colour = QColor(accent)
        line_colour.setAlphaF(opacity * 0.35)
        pen = QPen(line_colour, 1.0, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPoint(margin, int(middle)), QPoint(width - margin, int(middle)))

        chip_width, chip_height = 132, 34
        chip = QRectF((width - chip_width) / 2, middle - chip_height / 2, chip_width, chip_height)

        # The chip has to punch through the dashed rule behind it, so it is
        # filled solidly rather than tinted.
        fill = QColor(accent)
        fill.setAlphaF(opacity * 0.92)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(chip, RADIUS.pill, RADIUS.pill)

        label_font = QFont(self._state.settings.font_family)
        label_font.setPixelSize(TYPE.body)
        label_font.setWeight(QFont.Weight.Bold)
        painter.setFont(label_font)
        # Pick whichever of black or white actually reads on the accent.
        text_colour = QColor(255, 255, 255) if _is_dark(accent) else QColor(0, 0, 0)
        text_colour.setAlphaF(opacity)
        painter.setPen(text_colour)
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, "PAUSE")
        painter.setFont(self._ensure_font().font)

    def _paint_focus_band(
        self, painter: QPainter, focus_y: int, line_height: int, width: int
    ) -> None:
        top = focus_y - line_height * 0.9
        height = line_height * 1.9
        gradient = QLinearGradient(0, top, 0, top + height)
        tint = QColor(255, 255, 255) if _is_dark(self._colors["text"]) is False else QColor(0, 0, 0)
        for stop, alpha in ((0.0, 0), (0.5, 16), (1.0, 0)):
            colour = QColor(tint)
            colour.setAlpha(alpha)
            gradient.setColorAt(stop, colour)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRect(QRectF(0, top, width, height))

    def _paint_guides(self, painter: QPainter, focus_y: int, line_height: int, width: int) -> None:
        accent = QColor(self._colors["accent"])
        margin = self._margin()
        for offset in (-line_height * 0.9, line_height * 1.0):
            y = focus_y + offset
            gradient = QLinearGradient(margin, y, width - margin, y)
            for stop, alpha in ((0.0, 0), (0.5, 90), (1.0, 0)):
                colour = QColor(accent)
                colour.setAlpha(alpha)
                gradient.setColorAt(stop, colour)
            painter.setPen(QPen(gradient, 1.0))
            painter.drawLine(QPoint(margin, int(y)), QPoint(width - margin, int(y)))

    def _paint_countdown(self, painter: QPainter, value: int) -> None:
        accent = QColor(self._colors["accent"])
        centre = self.rect().center()
        radius = min(self.width(), self.height()) * 0.18

        track = QRectF(centre.x() - radius, centre.y() - radius, radius * 2, radius * 2)
        ring = QColor(accent)
        ring.setAlpha(45)
        painter.setPen(QPen(ring, 3.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(track)

        progress = QColor(accent)
        progress.setAlpha(220)
        painter.setPen(QPen(progress, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        span = int(-360 * 16 * self._countdown_scale)
        painter.drawArc(track, 90 * 16, span)

        font = QFont(self._state.settings.font_family)
        font.setPixelSize(max(48, int(radius * 1.15)))
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        text_colour = QColor(accent)
        text_colour.setAlphaF(min(1.0, 0.35 + self._countdown_scale * 0.65))
        painter.setPen(text_colour)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(value))

    def _paint_empty_state(self, painter: QPainter) -> None:
        text_colour = QColor(self._colors["text"])
        text_colour.setAlphaF(0.55)

        title_font = QFont(self._state.settings.font_family)
        title_font.setPixelSize(TYPE.heading)
        title_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.setPen(text_colour)

        area = self.rect().adjusted(SPACE.xxl, 0, -SPACE.xxl, 0)
        painter.drawText(
            QRect(area.x(), area.y(), area.width(), int(area.height() * 0.52)),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
            "Your script appears here",
        )

        hint_font = QFont(self._state.settings.font_family)
        hint_font.setPixelSize(TYPE.body_large)
        painter.setFont(hint_font)
        text_colour.setAlphaF(0.34)
        painter.setPen(text_colour)
        painter.drawText(
            QRect(area.x(), int(area.height() * 0.56), area.width(), area.height() // 2),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Type in the control panel, or press Load to open a file.\n\n"
            "[PAUSE]  ·  [CHAPTER Title]  ·  [[private note]]",
        )

    def _paint_hud(self, painter: QPainter) -> None:
        """A quiet corner readout: chapter, progress and remaining time."""
        if not self._state.settings.show_hud:
            return

        chapter = self._chapter_title_at(self._playback.transport.focus_line)
        progress = self._playback.transport.progress
        remaining = timing.remaining_seconds(
            self._playback.scroll_y,
            self._playback.transport.metrics.total_px,
            self._state.settings.speed,
        )

        parts = [f"{int(progress * 100)}%", timing.format_duration(remaining)]
        if chapter:
            parts.insert(0, chapter)
        text = "   ·   ".join(parts)

        font = QFont(self._state.settings.font_family)
        font.setPixelSize(TYPE.small)
        painter.setFont(font)

        colour = QColor(self._colors["text"])
        colour.setAlphaF(0.42)
        painter.setPen(colour)
        painter.drawText(
            self.rect().adjusted(SPACE.lg, SPACE.md, -SPACE.lg, -SPACE.md),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            text,
        )

    def _paint_edge_grips(self, painter: QPainter) -> None:
        """The drag handle at the top and the resize hint at the corner."""
        colour = QColor(self._colors["text"])

        colour.setAlphaF(0.30 if self._hover_drag_strip else 0.12)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        handle_width = 46
        painter.drawRoundedRect(QRectF((self.width() - handle_width) / 2, 9, handle_width, 4), 2, 2)

        colour.setAlphaF(0.22)
        painter.setPen(QPen(colour, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        corner_x, corner_y = self.width() - 8, self.height() - 8
        for offset in (0, 5, 10):
            painter.drawLine(
                QPoint(corner_x - 12 + offset, corner_y),
                QPoint(corner_x, corner_y - 12 + offset),
            )

    def _chapter_title_at(self, line_index: int) -> str:
        title = ""
        for start, name in self._layout.chapter_lines:
            if start <= line_index:
                title = name
            else:
                break
        return title

    def _on_position_changed(self, _scroll_y: float) -> None:
        """React to movement outside the paint pass.

        Chapter accounting and the notes window both mutate state, which must
        never happen while a widget is painting itself.
        """
        focus_line = self._playback.transport.focus_line
        if focus_line == self._last_focus_line:
            return
        self._last_focus_line = focus_line

        chapter = self._chapter_title_at(focus_line)
        if chapter and chapter != self._last_chapter:
            self._last_chapter = chapter
            self._playback.note_chapter(chapter)

        if self._notes_target is not None:
            self._notes_target.set_current_line(focus_line)

    def current_block_index(self) -> int:
        """Which script block the focus band is on — used to sync the editor."""
        line_index = self._playback.transport.focus_line
        if 0 <= line_index < len(self._layout.lines):
            return self._layout.lines[line_index].block_index
        return -1

    # ══ Touch overlay ═════════════════════════════════════════════════════════
    def _build_touch_bar(self) -> None:
        self._touch_bar = QWidget(self)
        self._touch_bar.setObjectName("TouchBar")
        row = QHBoxLayout(self._touch_bar)
        row.setContentsMargins(SPACE.md, SPACE.md, SPACE.md, SPACE.md)
        row.setSpacing(SPACE.md)

        self._touch_buttons: dict[str, QPushButton] = {}
        actions = (
            ("reset", "Back to start", self._playback.reset),
            ("play", "Play or pause", self._playback.toggle),
            ("minus", "Slower", lambda: self._nudge_speed(-0.2)),
            ("plus", "Faster", lambda: self._nudge_speed(0.2)),
        )
        for name, tooltip, handler in actions:
            button = QPushButton()
            button.setObjectName("TouchButton")
            button.setProperty("shape", "fixed")
            button.setFixedSize(MIN_TOUCH_TARGET + 12, MIN_TOUCH_TARGET + 12)
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(handler)
            row.addWidget(button)
            self._touch_buttons[name] = button

        self._touch_bar.setStyleSheet(
            "QWidget#TouchBar { background: rgba(12, 13, 17, 0.62);"
            f" border-radius: {RADIUS.xl}px; }}"
        )
        self._touch_bar.adjustSize()
        self._touch_bar.hide()

    def _style_touch_button(self, button: QPushButton) -> None:
        palette = self._palette
        if palette is None:
            return
        # An id selector, so these rules beat the application sheet's plain
        # QPushButton rule no matter which is applied first.
        radius = (MIN_TOUCH_TARGET + 12) // 2
        button.setStyleSheet(
            f"QPushButton#TouchButton {{ background: rgba(255,255,255,0.10);"
            f" border: 1px solid rgba(255,255,255,0.16);"
            # QSS box sizing measures content, so the 1px border on each side is
            # subtracted to land on the same 56px square setFixedSize asked for.
            f" border-radius: {radius}px; padding: 0;"
            f" min-width: {radius * 2 - 2}px; max-width: {radius * 2 - 2}px;"
            f" min-height: {radius * 2 - 2}px; max-height: {radius * 2 - 2}px; }}"
            f"QPushButton#TouchButton:hover {{ background: rgba(255,255,255,0.20);"
            f" border-color: {palette.accent}; }}"
            f"QPushButton#TouchButton:pressed {{ background: {palette.accent};"
            f" border-color: {palette.accent}; }}"
        )

    def _sync_touch_icons(self) -> None:
        if self._palette is None:
            return
        playing = self._playback.state is PlayState.PLAYING
        mapping = {
            "reset": ("rewind", self._palette.text),
            "play": ("pause" if playing else "play", self._palette.accent),
            "minus": ("minus", self._palette.text),
            "plus": ("plus", self._palette.text),
        }
        for key, (name, colour) in mapping.items():
            button = self._touch_buttons[key]
            button.setIcon(icons.icon(name, colour, 22))
            button.setIconSize(icons.icon_size(22))
        self._touch_buttons["play"].setToolTip("Pause" if playing else "Play")
        self._touch_buttons["play"].setAccessibleName(self._touch_buttons["play"].toolTip())

    def _position_touch_bar(self) -> None:
        bar = self._touch_bar
        bar.adjustSize()
        bar.move(
            (self.width() - bar.width()) // 2,
            self.height() - bar.height() - SPACE.xl,
        )
        bar.raise_()

    def _nudge_speed(self, delta: float) -> None:
        self._state.update_settings(speed=self._state.settings.speed + delta)

    # ══ Screen placement ══════════════════════════════════════════════════════
    def move_to_screen(self, screen: QScreen, fullscreen: bool) -> None:
        """Send the prompter to a specific display, windowed or full screen."""
        if self.isFullScreen():
            self.showNormal()

        handle = self.windowHandle()
        if handle is not None:
            handle.setScreen(screen)

        if fullscreen:
            self.setGeometry(screen.geometry())
            self.showFullScreen()
        else:
            available = screen.availableGeometry()
            size = self.size().boundedTo(available.size())
            self.resize(size)
            self.move(
                available.center().x() - size.width() // 2,
                available.center().y() - size.height() // 2,
            )
            self.show()
        self.raise_()
        self.activateWindow()

    def seek_to_block(self, block_index: int) -> None:
        """Jump the prompter to the first line of a script block."""
        self._ensure_layout()
        self._playback.seek_to_line(self._layout.line_for_block(block_index))

    def toggle_fullscreen(self) -> bool:
        if self.isFullScreen():
            self.showNormal()
            return False
        self.showFullScreen()
        return True

    # ══ Events ════════════════════════════════════════════════════════════════
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_key = ()
        self._relayout.start()
        self._position_touch_bar()
        self._grip.move(
            self.width() - self._grip.width() - 6, self.height() - self._grip.height() - 6
        )
        self._grip.raise_()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._position_touch_bar()
        self._grip.move(
            self.width() - self._grip.width() - 6, self.height() - self._grip.height() - 6
        )
        self._relayout.start()

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= DRAG_STRIP:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        inside = event.position().y() <= DRAG_STRIP
        if inside != self._hover_drag_strip:
            self._hover_drag_strip = inside
            self.setCursor(Qt.CursorShape.SizeAllCursor if inside else Qt.CursorShape.ArrowCursor)
            self.update()

        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_origin = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_drag_strip = False
        self.unsetCursor()
        self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event) -> None:
        steps = event.angleDelta().y() / 120.0
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._playback.seek_pixels(-steps * self._ensure_font().line_height * 2)
        else:
            self._nudge_speed(steps * 0.2)
        event.accept()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        line_height = self._ensure_font().line_height

        if key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._playback.toggle()
        elif key == Qt.Key.Key_Up:
            self._nudge_speed(0.2)
        elif key == Qt.Key.Key_Down:
            self._nudge_speed(-0.2)
        elif key == Qt.Key.Key_Left:
            self._playback.seek_pixels(-line_height * 2)
        elif key == Qt.Key.Key_Right:
            self._playback.seek_pixels(line_height * 2)
        elif key in (Qt.Key.Key_R, Qt.Key.Key_Escape):
            if self.isFullScreen() and key == Qt.Key.Key_Escape:
                self.showNormal()
            else:
                self._playback.reset()
        elif key == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)
            return
        event.accept()


# ══════════════════════════════════════════════════════════════════════════════
#  Small helpers
# ══════════════════════════════════════════════════════════════════════════════
def _is_dark(colour: QColor) -> bool:
    """True when the colour itself is dark (so it needs a light backdrop)."""
    return colour.lightness() < 128


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _mix(start: QColor, end: QColor, amount: float) -> QColor:
    if amount <= 0.0:
        return QColor(start)
    if amount >= 1.0:
        return QColor(end)
    return QColor(
        int(start.red() + (end.red() - start.red()) * amount),
        int(start.green() + (end.green() - start.green()) * amount),
        int(start.blue() + (end.blue() - start.blue()) * amount),
    )
