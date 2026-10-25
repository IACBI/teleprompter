"""Guards on the CI and release workflows.

Nothing else in the suite reads ``.github``, so these checks keep the pinned
actions and the release token scope from drifting back silently.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
USES_RE = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.MULTILINE)
PINNED_RE = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_sha(path):
    uses = USES_RE.findall(path.read_text(encoding="utf-8"))
    assert uses, f"no actions found in {path.name}"
    assert [u for u in uses if not PINNED_RE.match(u)] == []


STEP_START_RE = re.compile(r"^ {6}- ", re.MULTILINE)


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_every_checkout_keeps_its_token_out_of_git_config(path):
    """A checkout that persists credentials leaves the token readable to later steps."""
    steps = STEP_START_RE.split(path.read_text(encoding="utf-8"))[1:]
    checkouts = [step for step in steps if step.startswith("uses: actions/checkout@")]
    assert checkouts, f"no checkout steps found in {path.name}"
    assert all("persist-credentials: false" in step for step in checkouts)


def test_release_token_is_read_only_except_in_the_publish_job():
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    assert "\npermissions:\n  contents: read\n" in text
    assert text.count("contents: write") == 1


def test_ci_token_is_read_only():
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "\npermissions:\n  contents: read\n" in text
    assert "write" not in text
