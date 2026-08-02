"""Word wrapping and line layout.

Text measurement is injected as a ``measure`` callable so this module stays free
of Qt and testable with a deterministic fake metric. The renderer passes
``QFontMetrics.horizontalAdvance``; the PDF exporter passes its own printer-
resolution metric — the wrapping algorithm itself lives here exactly once.

Word offsets are stored **relative to the start of the line**, which means
changing text alignment only shifts a line's origin and never triggers a re-wrap.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from .script import BlockKind, Script

Measure = Callable[[str], int]

#: Hard ceiling on how many pieces one unbreakable word may be split into.
#: Protects the layout pass from a pathological multi-megabyte "word".
MAX_WORD_PIECES = 4096


class MeasureCache:
    """Memoises text measurement — scripts repeat words heavily."""

    __slots__ = ("_cache", "_measure", "hits", "misses")

    def __init__(self, measure: Measure) -> None:
        self._measure = measure
        self._cache: dict[str, int] = {}
        self.hits = 0
        self.misses = 0

    def __call__(self, text: str) -> int:
        cached = self._cache.get(text)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        width = self._measure(text)
        # Only memoise short tokens; caching whole long lines would grow unbounded.
        if len(text) <= 64:
            self._cache[text] = width
        return width


@dataclass(frozen=True)
class LayoutLine:
    """One rendered line of text after wrapping."""

    text: str
    kind: BlockKind
    block_index: int
    width: int
    words: tuple[str, ...] = ()
    #: x offset of each word measured from the start of the line.
    word_offsets: tuple[int, ...] = ()

    @property
    def is_drawable(self) -> bool:
        return bool(self.text)


@dataclass(frozen=True)
class Layout:
    """The wrapped form of a script at one particular width and font."""

    lines: tuple[LayoutLine, ...] = ()
    #: block index → index of the first line produced by that block.
    block_to_line: dict[int, int] = field(default_factory=dict)
    pause_lines: frozenset[int] = frozenset()
    notes_by_line: dict[int, str] = field(default_factory=dict)
    chapter_lines: tuple[tuple[int, str], ...] = ()

    def __len__(self) -> int:
        return len(self.lines)

    def line_for_block(self, block_index: int) -> int:
        """First line index of a block, clamped into range."""
        if not self.lines:
            return 0
        if block_index in self.block_to_line:
            return self.block_to_line[block_index]
        candidates = [v for k, v in self.block_to_line.items() if k <= block_index]
        return max(candidates) if candidates else 0


EMPTY_LAYOUT = Layout()


def break_long_word(word: str, max_width: int, measure: Measure) -> list[str]:
    """Split a word that cannot fit on one line into chunks that can.

    Uses exponential probing plus binary search so a one-million-character token
    costs O(log n) measurements per chunk instead of O(n).
    """
    if max_width <= 0 or not word:
        return [word]

    pieces: list[str] = []
    remaining = word
    while remaining:
        if measure(remaining) <= max_width:
            pieces.append(remaining)
            break
        if len(pieces) >= MAX_WORD_PIECES:
            # Safety valve: keep the text intact rather than splitting forever.
            pieces.append(remaining)
            break

        # Exponential probe for an upper bound that does not fit.
        low, high = 1, 2
        while high < len(remaining) and measure(remaining[:high]) <= max_width:
            low = high
            high *= 2
        high = min(high, len(remaining))

        # Binary search for the longest prefix that fits.
        while low < high:
            mid = (low + high + 1) // 2
            if measure(remaining[:mid]) <= max_width:
                low = mid
            else:
                high = mid - 1

        cut = max(1, low)  # always make progress, even if a single glyph overflows
        pieces.append(remaining[:cut])
        remaining = remaining[cut:]

    return pieces


def wrap_words(
    words: Iterable[str],
    max_width: int,
    measure: Measure,
    space_width: int,
) -> list[tuple[list[str], list[int], int]]:
    """Greedily wrap ``words``.

    Returns one ``(words, offsets, width)`` tuple per produced line, where
    ``offsets`` are x positions relative to the start of the line.
    """
    lines: list[tuple[list[str], list[int], int]] = []
    current: list[str] = []
    offsets: list[int] = []
    cursor = 0

    def flush() -> None:
        nonlocal current, offsets, cursor
        if current:
            lines.append((current, offsets, cursor))
        current, offsets, cursor = [], [], 0

    for word in words:
        width = measure(word)
        if width > max_width:
            # Unbreakable token wider than the column: flush, then hard-split it.
            flush()
            for piece in break_long_word(word, max_width, measure):
                lines.append(([piece], [0], measure(piece)))
            continue

        advance = width if not current else space_width + width
        if cursor + advance <= max_width or not current:
            offsets.append(cursor if not current else cursor + space_width)
            current.append(word)
            cursor += advance
        else:
            flush()
            offsets.append(0)
            current.append(word)
            cursor = width

    flush()
    return lines


def build_layout(
    script: Script,
    max_width: int,
    measure: Measure,
    space_width: int,
) -> Layout:
    """Wrap a whole script into renderable lines."""
    if not script.blocks:
        return EMPTY_LAYOUT

    cached = MeasureCache(measure)
    max_width = max(1, max_width)

    lines: list[LayoutLine] = []
    block_to_line: dict[int, int] = {}
    pause_lines: set[int] = set()
    notes_by_line: dict[int, str] = {}
    chapter_lines: list[tuple[int, str]] = []

    for block_index, block in enumerate(script.blocks):
        block_to_line[block_index] = len(lines)

        if block.note:
            notes_by_line[len(lines)] = block.note

        if block.kind is BlockKind.BLANK:
            lines.append(LayoutLine("", BlockKind.BLANK, block_index, 0))
        elif block.kind is BlockKind.PAUSE:
            pause_lines.add(len(lines))
            lines.append(LayoutLine(block.text, BlockKind.PAUSE, block_index, 0))
        else:
            if block.kind is BlockKind.CHAPTER:
                chapter_lines.append((len(lines), block.text))
            wrapped = wrap_words(block.text.split(), max_width, cached, space_width)
            if not wrapped:
                lines.append(LayoutLine("", BlockKind.BLANK, block_index, 0))
            for words, offsets, width in wrapped:
                lines.append(
                    LayoutLine(
                        text=" ".join(words),
                        kind=block.kind,
                        block_index=block_index,
                        width=width,
                        words=tuple(words),
                        word_offsets=tuple(offsets),
                    )
                )

    return Layout(
        lines=tuple(lines),
        block_to_line=block_to_line,
        pause_lines=frozenset(pause_lines),
        notes_by_line=notes_by_line,
        chapter_lines=tuple(chapter_lines),
    )


def line_origin_x(line_width: int, alignment: str, viewport_width: int, margin: int) -> int:
    """Left x for a line given ``alignment`` — ``left``, ``center`` or ``right``."""
    if alignment == "center":
        return max(margin, (viewport_width - line_width) // 2)
    if alignment == "right":
        return max(margin, viewport_width - margin - line_width)
    return margin
