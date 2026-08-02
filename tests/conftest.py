"""Shared fixtures.

The layout engine takes an injected text measurer, so tests use a deterministic
monospace-like metric instead of loading real fonts.
"""

from __future__ import annotations

import getpass
import tempfile
from pathlib import Path

import pytest

CHAR_WIDTH = 10
SPACE_WIDTH = 10


def pytest_configure(config: pytest.Config) -> None:
    """Keep the temp root on an ASCII path.

    pytest names its base temp directory ``pytest-of-<os user>``. Windows cannot
    create that directory when the account's display name contains characters
    outside the BMP, which makes every ``tmp_path`` test fail with WinError 5.
    Redirecting the base temp keeps those tests runnable on such machines while
    leaving the default behaviour alone everywhere else.
    """
    if config.option.basetemp is not None:
        return
    try:
        getpass.getuser().encode("ascii")
    except (UnicodeEncodeError, OSError, ImportError):
        config.option.basetemp = Path(tempfile.gettempdir()) / "pytest-teleprompter"


def fake_measure(text: str) -> int:
    """Every character is exactly ``CHAR_WIDTH`` wide."""
    return len(text) * CHAR_WIDTH


@pytest.fixture
def measure():
    return fake_measure


@pytest.fixture
def space_width() -> int:
    return SPACE_WIDTH
