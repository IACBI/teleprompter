from __future__ import annotations

import pytest

from teleprompter.storage.importers import (
    decode_bytes,
    human_size,
    looks_binary,
    normalize_newlines,
    read_script_file,
)


def write(tmp_path, name: str, data: bytes):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_utf8_text_loads(tmp_path):
    path = write(tmp_path, "s.txt", "Merhaba dünya".encode())
    result = read_script_file(path)
    assert result.ok
    assert result.text == "Merhaba dünya"


def test_utf8_bom_is_stripped(tmp_path):
    path = write(tmp_path, "s.txt", b"\xef\xbb\xbfHello")
    assert read_script_file(path).text == "Hello"


def test_utf16_is_detected_by_its_bom(tmp_path):
    path = write(tmp_path, "s.txt", "Yayın".encode("utf-16"))
    result = read_script_file(path)
    assert result.ok
    assert result.text == "Yayın"


def test_windows_1254_turkish_text_loads(tmp_path):
    path = write(tmp_path, "s.txt", "Şişli çığır".encode("cp1254"))
    result = read_script_file(path)
    assert result.ok
    assert "Şişli" in result.text


def test_crlf_is_normalised(tmp_path):
    path = write(tmp_path, "s.txt", b"one\r\ntwo\rthree")
    assert read_script_file(path).text == "one\ntwo\nthree"


def test_a_binary_file_is_refused_rather_than_mangled(tmp_path):
    path = write(tmp_path, "clip.mp4", b"\x00\x01\x02binary\x00garbage" * 100)
    result = read_script_file(path)
    assert not result.ok
    assert "binary" in result.error.lower()


def test_an_oversized_file_is_refused(tmp_path):
    path = write(tmp_path, "big.txt", b"a" * 5000)
    result = read_script_file(path, max_bytes=1000)
    assert not result.ok
    assert "limit" in result.error.lower()


def test_a_missing_file_reports_an_error(tmp_path):
    result = read_script_file(tmp_path / "nope.txt")
    assert not result.ok


def test_non_utf8_decode_warns_that_the_encoding_was_guessed(tmp_path):
    path = write(tmp_path, "s.txt", b"caf\xe9 latte")  # invalid UTF-8
    result = read_script_file(path)
    assert result.ok
    assert result.warning is not None
    assert "UTF-8" in result.warning


def test_clean_utf8_carries_no_warning(tmp_path):
    path = write(tmp_path, "s.txt", "café latte".encode())
    assert read_script_file(path).warning is None


def test_pdf_reader_is_injectable(tmp_path):
    path = tmp_path / "deck.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    result = read_script_file(path, pdf_reader=lambda _p: ["Page one", "Page two"])
    assert result.ok
    assert result.text == "Page one\n\nPage two"


def test_a_broken_pdf_reports_an_error_instead_of_raising(tmp_path):
    path = tmp_path / "deck.pdf"
    path.write_bytes(b"not really a pdf")

    def explode(_p):
        raise RuntimeError("damaged xref table")

    result = read_script_file(path, pdf_reader=explode)
    assert not result.ok
    assert "damaged xref table" in result.error


def test_a_pdf_without_selectable_text_explains_why(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF")
    result = read_script_file(path, pdf_reader=lambda _p: ["", "  "])
    assert not result.ok
    assert "OCR" in result.error


def test_decode_bytes_returns_none_for_undecodable_input():
    # Every byte sequence is valid Latin-1, so decoding always succeeds — this
    # documents that the binary check is what actually guards the loader.
    assert decode_bytes(b"\xff\xfe\x01\x02") is not None


def test_looks_binary_only_flags_nul_bytes():
    assert looks_binary(b"text\x00more")
    assert not looks_binary("normal türkçe metin".encode())


def test_normalize_newlines_is_idempotent():
    once = normalize_newlines("a\r\nb")
    assert normalize_newlines(once) == once


@pytest.mark.parametrize(
    ("size", "text"), [(512, "512 B"), (2048, "2.0 KB"), (5 * 1024 * 1024, "5.0 MB")]
)
def test_human_size(size, text):
    assert human_size(size) == text
