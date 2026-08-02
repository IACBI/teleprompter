from __future__ import annotations

from teleprompter.core.layout import (
    MeasureCache,
    break_long_word,
    build_layout,
    line_origin_x,
    wrap_words,
)
from teleprompter.core.script import BlockKind, parse_script

from .conftest import CHAR_WIDTH, SPACE_WIDTH, fake_measure


def test_words_fitting_on_one_line_stay_together():
    lines = wrap_words(["ab", "cd"], 100, fake_measure, SPACE_WIDTH)
    assert len(lines) == 1
    assert lines[0][0] == ["ab", "cd"]


def test_wrapping_happens_at_the_column_edge():
    # "aaaa"=40, +space+"bbbb"=90, +space+"cccc"=140 > 100
    lines = wrap_words(["aaaa", "bbbb", "cccc"], 100, fake_measure, SPACE_WIDTH)
    assert [words for words, _, _ in lines] == [["aaaa", "bbbb"], ["cccc"]]


def test_word_offsets_are_relative_to_the_line_start():
    lines = wrap_words(["ab", "cd"], 200, fake_measure, SPACE_WIDTH)
    _, offsets, width = lines[0]
    assert offsets == [0, 2 * CHAR_WIDTH + SPACE_WIDTH]
    assert width == 2 * CHAR_WIDTH + SPACE_WIDTH + 2 * CHAR_WIDTH


def test_a_word_wider_than_the_column_is_split():
    pieces = break_long_word("x" * 25, 100, fake_measure)
    assert all(fake_measure(p) <= 100 for p in pieces)
    assert "".join(pieces) == "x" * 25


def test_splitting_never_loses_characters_on_a_huge_token():
    word = "y" * 5000
    pieces = break_long_word(word, 100, fake_measure)
    assert "".join(pieces) == word


def test_split_makes_progress_even_when_one_glyph_overflows():
    pieces = break_long_word("abc", 1, fake_measure)
    assert pieces == ["a", "b", "c"]


def test_unbreakable_word_gets_its_own_lines():
    lines = wrap_words(["ok", "z" * 30], 100, fake_measure, SPACE_WIDTH)
    assert lines[0][0] == ["ok"]
    assert "".join("".join(w) for w, _, _ in lines[1:]) == "z" * 30


def test_measure_cache_avoids_repeat_measurement():
    cache = MeasureCache(fake_measure)
    cache("hello")
    cache("hello")
    assert cache.hits == 1
    assert cache.misses == 1


def test_measure_cache_does_not_retain_long_strings():
    cache = MeasureCache(fake_measure)
    long_text = "q" * 200
    cache(long_text)
    cache(long_text)
    assert cache.hits == 0


def test_layout_maps_blocks_to_their_first_line():
    script = parse_script("aaaa bbbb cccc\nsecond")
    layout = build_layout(script, 100, fake_measure, SPACE_WIDTH)
    assert layout.block_to_line[0] == 0
    assert layout.block_to_line[1] == 2  # first block wrapped onto two lines


def test_layout_records_pause_lines_after_wrapping():
    script = parse_script("aaaa bbbb cccc\n[PAUSE]\nafter")
    layout = build_layout(script, 100, fake_measure, SPACE_WIDTH)
    (pause_line,) = layout.pause_lines
    assert layout.lines[pause_line].kind is BlockKind.PAUSE


def test_layout_attaches_notes_to_the_first_line_of_a_block():
    script = parse_script("aaaa bbbb cccc [[breathe]]")
    layout = build_layout(script, 100, fake_measure, SPACE_WIDTH)
    assert layout.notes_by_line == {0: "breathe"}


def test_layout_lists_chapter_lines():
    script = parse_script("[CHAPTER Intro]\nhello")
    layout = build_layout(script, 500, fake_measure, SPACE_WIDTH)
    assert layout.chapter_lines == ((0, "Intro"),)


def test_blank_lines_survive_layout():
    script = parse_script("a\n\nb")
    layout = build_layout(script, 500, fake_measure, SPACE_WIDTH)
    assert [line.kind for line in layout.lines] == [
        BlockKind.TEXT,
        BlockKind.BLANK,
        BlockKind.TEXT,
    ]


def test_empty_script_produces_empty_layout():
    layout = build_layout(parse_script(""), 500, fake_measure, SPACE_WIDTH)
    assert len(layout) == 0


def test_zero_width_does_not_hang():
    script = parse_script("some words here")
    layout = build_layout(script, 0, fake_measure, SPACE_WIDTH)
    assert len(layout) > 0


def test_line_origin_respects_alignment():
    assert line_origin_x(100, "left", 500, 40) == 40
    assert line_origin_x(100, "center", 500, 40) == 200
    assert line_origin_x(100, "right", 500, 40) == 360


def test_line_origin_never_crosses_the_margin():
    assert line_origin_x(900, "center", 500, 40) == 40
    assert line_origin_x(900, "right", 500, 40) == 40
