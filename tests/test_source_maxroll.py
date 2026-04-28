"""Tests for MaxrollSource — uses fixtures, not network."""

from __future__ import annotations

from pathlib import Path

import pytest

from d4_build.cache import Cache
from d4_build.sources.maxroll import MaxrollSource
from tests.conftest import require_maxroll_fixture


@pytest.fixture
def source(tmp_path: Path) -> MaxrollSource:
    guide_path = require_maxroll_fixture("blizzard-sorcerer-guide.html")
    planner_path = require_maxroll_fixture("planner-vw1uz0be.html")

    cache = Cache(db_path=tmp_path / "cache.db")
    fixtures = {
        "https://maxroll.gg/d4/build-guides/blizzard-sorcerer-guide": (
            guide_path.read_text()
        ),
        "https://maxroll.gg/d4/planner/vw1uz0be": planner_path.read_text(),
    }

    def fake_fetch(url: str) -> str:
        return fixtures[url]

    return MaxrollSource(cache=cache, fetcher=fake_fetch)


def test_get_guide_returns_meta(source: MaxrollSource) -> None:
    meta = source.get_guide("blizzard-sorcerer-guide")
    assert meta.archetype == "Blizzard"
    assert meta.class_name == "Sorcerer"
    assert meta.planner_id == "vw1uz0be"


def test_get_planner_returns_profile_data(source: MaxrollSource) -> None:
    profile = source.get_planner("vw1uz0be")
    assert profile.class_name == "Sorcerer"
    assert "Blizzard" in profile.skill_names


def test_second_call_uses_cache(source: MaxrollSource) -> None:
    """Verify the cache is consulted on the second call."""
    calls = {"n": 0}
    real = source._fetcher

    def counting(url: str) -> str:
        calls["n"] += 1
        return real(url)

    source._fetcher = counting  # type: ignore[assignment]
    source.get_guide("blizzard-sorcerer-guide")
    source.get_guide("blizzard-sorcerer-guide")
    assert calls["n"] == 1
