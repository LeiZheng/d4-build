"""Tests for the Maxroll planner Remix-context parser.

Fixture: tests/fixtures/maxroll/planner-vw1uz0be.html  — full saved planner page
"""

from __future__ import annotations

import pytest

from d4_build.parsers.planner_remix import (
    PlannerProfileData,
    extract_remix_context,
    parse_planner_html,
)
from tests.conftest import require_maxroll_fixture


@pytest.fixture
def planner_html() -> str:
    return require_maxroll_fixture("planner-vw1uz0be.html").read_text()


def test_extract_remix_context_returns_dict(planner_html: str) -> None:
    """The Remix context blob (window.__remixContext = {...}) is JSON-extractable."""
    ctx = extract_remix_context(planner_html)
    assert isinstance(ctx, dict)
    assert "state" in ctx
    assert "loaderData" in ctx["state"]
    assert "d4planner-by-id" in ctx["state"]["loaderData"]


def test_parse_planner_returns_typed_profile(planner_html: str) -> None:
    """Top-level helper returns a typed PlannerProfileData."""
    profile = parse_planner_html(planner_html)
    assert isinstance(profile, PlannerProfileData)
    assert profile.class_name == "Sorcerer"
    assert profile.id == "vw1uz0be"
    # The build name is "S12 Blizzard Sorc"
    assert "Blizzard" in profile.name
    # Item names from search_metadata
    assert "Heir of Perdition" in profile.item_names
    assert "Ring of Starless Skies" in profile.item_names
    # Skill names
    assert "Blizzard" in profile.skill_names
    assert "Frost Bolt" in profile.skill_names


def test_parse_planner_has_variants(planner_html: str) -> None:
    """Each planner has multiple build variants (Leveling, Starter, Ancestral, Mythic, ...)."""
    profile = parse_planner_html(planner_html)
    variant_names = [v.name for v in profile.variants]
    assert "Mythic" in variant_names
    assert "Leveling" in variant_names


def test_endgame_variant_has_skill_bar(planner_html: str) -> None:
    """The Mythic variant (endgame) has a 6-skill skillBar."""
    profile = parse_planner_html(planner_html)
    mythic = next(v for v in profile.variants if v.name == "Mythic")
    assert len(mythic.skill_bar) == 6
    # Each entry is a Maxroll skill ID, e.g. 'Sorcerer_Blizzard'
    assert any("Blizzard" in s for s in mythic.skill_bar)


def test_extract_remix_context_handles_missing(planner_html: str) -> None:
    """If the page has no remix context (e.g. it's a 404), raise."""
    with pytest.raises(ValueError, match="remix"):
        extract_remix_context("<html><body>nothing here</body></html>")
