"""Script model and tag parsing.

The teleprompter understands three inline tags:

``[PAUSE]``
    On its own line. Scrolling stops when this line reaches the focus band.
``[[note text]]``
    Anywhere in a line. Stripped from the prompter text and shown only in the
    presenter notes window. Several notes on one line are joined.
``[CHAPTER Title]``
    On its own line. Becomes a navigable chapter heading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

PAUSE_TAG = "[PAUSE]"

NOTE_RE = re.compile(r"\[\[(.+?)\]\]", re.DOTALL)
PAUSE_RE = re.compile(r"^\[\s*PAUSE\s*\]$", re.IGNORECASE)
CHAPTER_RE = re.compile(r"^\[\s*CHAPTER\b\s*(.*?)\s*\]$", re.IGNORECASE)

NOTE_SEPARATOR = "  ·  "


class BlockKind(Enum):
    """What a parsed source line turned into."""

    TEXT = "text"
    BLANK = "blank"
    PAUSE = "pause"
    CHAPTER = "chapter"


@dataclass(frozen=True)
class Block:
    """One logical line of the script, with its tags already resolved.

    ``text`` is what the audience-facing prompter renders; tags never appear in
    it. ``source_line`` is the 0-based line index in the original script, which
    the editor uses to map a prompter position back to a cursor position.
    """

    kind: BlockKind
    text: str
    note: str | None
    source_line: int
    word_count: int


@dataclass(frozen=True)
class Chapter:
    """A navigable marker pointing at a block index."""

    title: str
    block_index: int


@dataclass(frozen=True)
class Script:
    """An immutable parsed script."""

    raw: str
    blocks: tuple[Block, ...]
    chapters: tuple[Chapter, ...]
    word_count: int

    @property
    def is_empty(self) -> bool:
        return not any(b.text for b in self.blocks)

    def notes_by_block(self) -> dict[int, str]:
        """Map block index → note text, for blocks that carry one."""
        return {i: b.note for i, b in enumerate(self.blocks) if b.note}

    def pause_blocks(self) -> frozenset[int]:
        return frozenset(i for i, b in enumerate(self.blocks) if b.kind is BlockKind.PAUSE)

    def chapter_at(self, block_index: int) -> Chapter | None:
        """The chapter that ``block_index`` falls under, if any."""
        found: Chapter | None = None
        for chapter in self.chapters:
            if chapter.block_index <= block_index:
                found = chapter
            else:
                break
        return found


EMPTY_SCRIPT = Script(raw="", blocks=(), chapters=(), word_count=0)


def extract_notes(line: str) -> tuple[str, str | None]:
    """Split a raw line into (visible text, joined note or None).

    Removing a mid-sentence note leaves a gap, so whitespace is collapsed —
    otherwise ``Block.text`` would carry double spaces the reader never typed.
    """
    notes = [m.strip() for m in NOTE_RE.findall(line)]
    visible = " ".join(NOTE_RE.sub(" ", line).split())
    note = NOTE_SEPARATOR.join(n for n in notes if n) or None
    return visible, note


def count_words(text: str) -> int:
    """Count words the way a reader would — punctuation-only tokens don't count."""
    return sum(1 for word in text.split() if any(ch.isalnum() for ch in word))


def parse_script(text: str) -> Script:
    """Parse raw script text into an immutable :class:`Script`."""
    if not text:
        return EMPTY_SCRIPT

    blocks: list[Block] = []
    chapters: list[Chapter] = []
    total_words = 0

    for source_line, raw_line in enumerate(text.split("\n")):
        visible, note = extract_notes(raw_line)

        if not visible:
            kind, block_text, words = BlockKind.BLANK, "", 0
        elif PAUSE_RE.match(visible):
            kind, block_text, words = BlockKind.PAUSE, PAUSE_TAG, 0
        elif (chapter_match := CHAPTER_RE.match(visible)) is not None:
            title = chapter_match.group(1).strip() or f"Chapter {len(chapters) + 1}"
            kind, block_text, words = BlockKind.CHAPTER, title, 0
            chapters.append(Chapter(title=title, block_index=len(blocks)))
        else:
            kind, block_text = BlockKind.TEXT, visible
            words = count_words(visible)
            total_words += words

        blocks.append(
            Block(
                kind=kind,
                text=block_text,
                note=note,
                source_line=source_line,
                word_count=words,
            )
        )

    return Script(
        raw=text,
        blocks=tuple(blocks),
        chapters=tuple(chapters),
        word_count=total_words,
    )
