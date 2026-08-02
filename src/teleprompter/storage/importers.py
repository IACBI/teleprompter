"""Loading scripts from disk.

Deliberately defensive: a teleprompter is pointed at whatever file a user
happens to pick, so this module caps how much it will read, refuses binaries
instead of rendering mojibake, and never lets a broken PDF escape as an
exception.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

#: Roughly a 4-million-word script — far past any real use, small enough that a
#: mis-clicked video file cannot exhaust memory.
MAX_TEXT_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 2000

#: Byte-order marks checked before the encoding probe, because Latin-1 would
#: otherwise "successfully" decode UTF-16 into garbage.
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)

#: Tried in order once no BOM matched. Latin-1 is last and always succeeds,
#: which is why the binary check has to happen before this runs.
ENCODINGS: tuple[str, ...] = ("utf-8", "cp1254", "cp1252", "cp1250", "latin-1")

#: Encodings that were positively identified rather than guessed. Anything else
#: gets a "the text may be wrong" warning attached to the import result.
_UNAMBIGUOUS_ENCODINGS = frozenset({"utf-8", "utf-8-sig", "utf-16", "utf-32", "pdf"})

_BINARY_SNIFF_BYTES = 8192

PdfReader = Callable[[Path], list[str]]


@dataclass(frozen=True)
class ImportResult:
    """Outcome of a script import."""

    text: str = ""
    error: str | None = None
    warning: str | None = None
    encoding: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None


def human_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def has_text_bom(raw: bytes) -> bool:
    """True if the file announces a Unicode encoding up front."""
    return any(raw.startswith(bom) for bom, _ in _BOMS)


def looks_binary(sample: bytes) -> bool:
    """A NUL byte in the first block is the classic 'not text' signal.

    Only meaningful for files without a BOM — UTF-16 and UTF-32 text is full of
    legitimate NUL bytes, so callers check :func:`has_text_bom` first.
    """
    return b"\x00" in sample


def normalize_newlines(text: str) -> str:
    """Collapse CRLF/CR to LF so wrapping and line indices stay consistent."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def decode_bytes(raw: bytes) -> tuple[str, str] | None:
    """Decode ``raw`` using BOM detection then an encoding probe."""
    for bom, encoding in _BOMS:
        if raw.startswith(bom):
            try:
                return raw.decode(encoding), encoding
            except (UnicodeDecodeError, LookupError):
                break
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _default_pdf_reader(path: Path) -> list[str]:
    import fitz

    doc = fitz.open(str(path))
    try:
        if doc.page_count > MAX_PDF_PAGES:
            raise ValueError(
                f"This PDF has {doc.page_count} pages; the import limit is {MAX_PDF_PAGES}."
            )
        return [page.get_text() for page in doc]
    finally:
        doc.close()


def pdf_available() -> bool:
    try:
        import fitz  # noqa: F401
    except ImportError:
        return False
    return True


def read_pdf(path: Path, reader: PdfReader | None = None) -> ImportResult:
    """Extract text from a PDF, or explain why it could not be read."""
    if reader is None and not pdf_available():
        return ImportResult(
            error="Reading PDF files needs PyMuPDF.\n\nInstall it with:  pip install PyMuPDF"
        )
    try:
        pages = (reader or _default_pdf_reader)(path)
    except ValueError as exc:
        return ImportResult(error=str(exc))
    except Exception as exc:
        return ImportResult(error=f"This PDF could not be read.\n\n{exc}")

    text = normalize_newlines("\n\n".join(pages).strip())
    if not text:
        return ImportResult(
            error="No selectable text was found in this PDF.\n"
            "Scanned documents need OCR before they can be imported."
        )
    return ImportResult(text=text, encoding="pdf")


def read_script_file(
    path: str | Path,
    *,
    max_bytes: int = MAX_TEXT_BYTES,
    pdf_reader: PdfReader | None = None,
) -> ImportResult:
    """Read a ``.txt`` or ``.pdf`` script from disk."""
    target = Path(path)

    if target.suffix.lower() == ".pdf":
        return read_pdf(target, pdf_reader)

    try:
        size = target.stat().st_size
    except OSError as exc:
        return ImportResult(error=f"This file could not be opened.\n\n{exc}")

    if size > max_bytes:
        return ImportResult(
            error=f"This file is {human_size(size)}, larger than the "
            f"{human_size(max_bytes)} import limit."
        )

    try:
        raw = target.read_bytes()
    except OSError as exc:
        return ImportResult(error=f"This file could not be read.\n\n{exc}")

    if not has_text_bom(raw) and looks_binary(raw[:_BINARY_SNIFF_BYTES]):
        return ImportResult(
            error="This looks like a binary file, not a script.\nPick a .txt or .pdf file instead."
        )

    decoded = decode_bytes(raw)
    if decoded is None:
        return ImportResult(
            error="This file could not be decoded with any known encoding.\n"
            "Re-save it as UTF-8 and try again."
        )

    text, encoding = decoded
    warning = None
    if encoding not in _UNAMBIGUOUS_ENCODINGS:
        # Every byte sequence is valid in a legacy 8-bit codepage, so a
        # successful decode there is a guess, not a detection. Say so.
        warning = (
            f"This file is not valid UTF-8; it was read as {encoding}. "
            "Some characters may be wrong — re-save it as UTF-8 for an exact result."
        )
    return ImportResult(text=normalize_newlines(text), encoding=encoding, warning=warning)
