"""Shared pytest config.

The test suite depends on saved Maxroll HTML fixtures for snapshot/integration
testing, but those fixtures are gitignored (Maxroll content is copyrighted).
Tests that read a missing Maxroll fixture should skip cleanly rather than
fail. This module exposes a single helper for that pattern.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MAXROLL_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "maxroll"
D4DATA_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "d4data"


def require_maxroll_fixture(name: str) -> Path:
    """Return the fixture path or skip the test if the fixture is missing.

    Use as the first line of a fixture-needing pytest function:

        path = require_maxroll_fixture("blizzard-sorcerer-guide.html")
        html = path.read_text()
    """
    p = MAXROLL_FIXTURE_DIR / name
    if not p.exists():
        pytest.skip(
            f"Maxroll fixture {name!r} not present. "
            f"It's gitignored (copyright); tests skip cleanly without it. "
            f"Drop a saved Maxroll HTML page at {p} to enable this test."
        )
    return p
