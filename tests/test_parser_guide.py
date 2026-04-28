"""Tests for the Maxroll guide-page HTML parser.

Fixture: tests/fixtures/maxroll/blizzard-sorcerer-guide.html
"""

from __future__ import annotations

import pytest

from d4_build.parsers.guide_html import GuideMeta, parse_guide_html
from tests.conftest import require_maxroll_fixture


@pytest.fixture
def guide_html() -> str:
    return require_maxroll_fixture("blizzard-sorcerer-guide.html").read_text()


def test_parse_guide_returns_typed_meta(guide_html: str) -> None:
    meta = parse_guide_html(guide_html)
    assert isinstance(meta, GuideMeta)


def test_archetype_extracted_from_h1(guide_html: str) -> None:
    meta = parse_guide_html(guide_html)
    # Archetype is the first word(s) of the title before the class name.
    assert meta.archetype == "Blizzard"
    assert meta.class_name == "Sorcerer"


def test_role_extracted_from_h1(guide_html: str) -> None:
    """Role is "Endgame" / "Leveling" / "Speed Farm" — derived from the H1."""
    meta = parse_guide_html(guide_html)
    assert meta.role == "Endgame"


def test_season_extracted_from_h1(guide_html: str) -> None:
    meta = parse_guide_html(guide_html)
    assert "Season 12" in meta.season


def test_planner_id_extracted_from_data_attr(guide_html: str) -> None:
    """The first data-d4-profile attribute carries the planner profile ID."""
    meta = parse_guide_html(guide_html)
    assert meta.planner_id == "vw1uz0be"


def test_referenced_entities_extracted(guide_html: str) -> None:
    """data-d4-id spans give us every game-entity reference in the article body."""
    meta = parse_guide_html(guide_html)
    # We expect specific known references: Blizzard skill (291403), Glacial aspect, etc.
    ids = {ref.id for ref in meta.referenced_entities}
    names = {ref.name for ref in meta.referenced_entities}
    assert 291403 in ids  # Blizzard
    assert "Blizzard" in names
    assert any("Sorc" not in n for n in names)  # sanity: we got actual names


def test_section_text_extracted_for_skill_rotation(guide_html: str) -> None:
    """We extract prose for known section headers (e.g., "Skill Rotation")."""
    meta = parse_guide_html(guide_html)
    rotation = meta.sections.get("Skill Rotation", "")
    # Rotation prose should mention key skills
    assert len(rotation) > 50
