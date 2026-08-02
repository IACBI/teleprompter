from __future__ import annotations

import pytest

from teleprompter.core.script import (
    BlockKind,
    count_words,
    extract_notes,
    parse_script,
)


def test_empty_text_parses_to_empty_script():
    script = parse_script("")
    assert script.blocks == ()
    assert script.word_count == 0
    assert script.is_empty


def test_plain_paragraphs_are_text_blocks():
    script = parse_script("Hello world\nSecond line")
    assert [b.kind for b in script.blocks] == [BlockKind.TEXT, BlockKind.TEXT]
    assert script.word_count == 4


def test_blank_lines_are_preserved_as_blocks():
    script = parse_script("one\n\ntwo")
    assert [b.kind for b in script.blocks] == [
        BlockKind.TEXT,
        BlockKind.BLANK,
        BlockKind.TEXT,
    ]


@pytest.mark.parametrize("raw", ["[PAUSE]", "[pause]", "[ PAUSE ]", "  [Pause]  "])
def test_pause_tag_is_case_and_space_tolerant(raw):
    script = parse_script(raw)
    assert script.blocks[0].kind is BlockKind.PAUSE
    assert script.pause_blocks() == {0}


def test_pause_tag_inside_a_sentence_is_not_a_marker():
    script = parse_script("say [PAUSE] here")
    assert script.blocks[0].kind is BlockKind.TEXT


def test_note_is_stripped_from_visible_text():
    visible, note = extract_notes("Welcome [[smile now]] everyone")
    assert visible == "Welcome everyone"
    assert note == "smile now"


def test_multiple_notes_on_one_line_are_joined():
    _, note = extract_notes("[[first]] text [[second]]")
    assert note is not None
    assert "first" in note and "second" in note


def test_note_only_line_becomes_blank_but_keeps_the_note():
    script = parse_script("[[just a note]]")
    assert script.blocks[0].kind is BlockKind.BLANK
    assert script.notes_by_block() == {0: "just a note"}


def test_chapter_tag_creates_a_navigable_marker():
    script = parse_script("[CHAPTER Opening]\nHello")
    assert script.blocks[0].kind is BlockKind.CHAPTER
    assert script.blocks[0].text == "Opening"
    assert script.chapters[0].title == "Opening"
    assert script.chapters[0].block_index == 0


def test_untitled_chapter_gets_a_number():
    script = parse_script("[CHAPTER]\ntext\n[CHAPTER]")
    assert [c.title for c in script.chapters] == ["Chapter 1", "Chapter 2"]


def test_chapter_at_finds_the_enclosing_chapter():
    script = parse_script("[CHAPTER A]\none\n[CHAPTER B]\ntwo")
    assert script.chapter_at(1).title == "A"
    assert script.chapter_at(3).title == "B"


def test_chapter_at_returns_none_before_the_first_chapter():
    script = parse_script("intro\n[CHAPTER A]")
    assert script.chapter_at(0) is None


def test_markers_do_not_count_as_words():
    script = parse_script("[CHAPTER Intro]\n[PAUSE]\ntwo real words")
    assert script.word_count == 3


def test_punctuation_only_tokens_are_not_words():
    assert count_words("hello — world ...") == 2


def test_source_line_survives_parsing():
    script = parse_script("a\nb\nc")
    assert [b.source_line for b in script.blocks] == [0, 1, 2]
