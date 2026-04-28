"""Tests for maxroll_index.list_class_archetypes against the saved fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from d4_build.cache import Cache
from d4_build.sources.maxroll import MaxrollSource
from d4_build.sources.maxroll_index import _parse_tierlist_html, list_class_archetypes
from tests.conftest import require_maxroll_fixture


def test_parse_tierlist_extracts_known_archetypes() -> None:
    html = require_maxroll_fixture("sorcerer-endgame-tierlist.html").read_text()
    summaries = _parse_tierlist_html(html, "Sorcerer", "endgame")
    archetypes = {s.archetype for s in summaries}
    assert "Blizzard" in archetypes
    assert "Ice Shards" in archetypes
    assert "Hydra" in archetypes
    assert "Ball Lightning" in archetypes


def test_parse_tierlist_strips_class_suffix() -> None:
    html = require_maxroll_fixture("sorcerer-endgame-tierlist.html").read_text()
    summaries = _parse_tierlist_html(html, "Sorcerer", "endgame")
    for s in summaries:
        assert "Sorc" not in s.archetype, f"archetype should be cleaned: {s.archetype!r}"


def test_list_class_archetypes_dedupes_across_roles(tmp_path: Path) -> None:
    """When the same build appears under multiple roles, it's listed once."""
    cache = Cache(db_path=tmp_path / "cache.db")
    sample_html = require_maxroll_fixture("sorcerer-endgame-tierlist.html").read_text()

    fixtures = {
        "https://maxroll.gg/d4/tierlists/sorcerer-endgame-tier-list": sample_html,
        "https://maxroll.gg/d4/tierlists/sorcerer-leveling-tier-list": sample_html,
        "https://maxroll.gg/d4/tierlists/sorcerer-push-tier-list": sample_html,
        "https://maxroll.gg/d4/tierlists/sorcerer-speedfarming-tier-list": sample_html,
    }

    def fetch(url: str) -> str:
        if url in fixtures:
            return fixtures[url]
        raise RuntimeError(f"unexpected url: {url}")

    source = MaxrollSource(cache=cache, fetcher=fetch)
    summaries = list_class_archetypes(source, "sorcerer")
    assert len(summaries) > 0
    # Dedup: archetype slugs should be unique
    ids = [s.id for s in summaries]
    assert len(ids) == len(set(ids))
