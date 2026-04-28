"""Reconcile guide+planner -> Build."""

from __future__ import annotations

import pytest

from d4_build.model import GearSlot
from d4_build.parsers.guide_html import parse_guide_html
from d4_build.parsers.planner_remix import parse_planner_html
from d4_build.reconcile import reconcile
from tests.conftest import require_maxroll_fixture


@pytest.fixture
def real_build():
    guide_html = require_maxroll_fixture("blizzard-sorcerer-guide.html").read_text()
    planner_html = require_maxroll_fixture("planner-vw1uz0be.html").read_text()
    meta = parse_guide_html(guide_html)
    profile = parse_planner_html(planner_html)
    return reconcile(
        meta,
        profile,
        guide_url="https://maxroll.gg/d4/build-guides/blizzard-sorcerer-guide",
    )


def test_build_is_blizzard_sorcerer(real_build) -> None:
    assert real_build.archetype == "Blizzard"
    assert real_build.class_.name == "Sorcerer"
    assert real_build.role == "Endgame"
    assert "Season 12" in real_build.season


def test_build_has_six_skills(real_build) -> None:
    assert len(real_build.skills_in_order) == 6
    assert real_build.skills_in_order[0].name == "Blizzard"


def test_build_has_gear_with_uniques_flagged(real_build) -> None:
    """Some items in the Blizzard Sorc build are uniques (Heir of Perdition, Temerity, etc)."""
    assert len(real_build.gear) > 0
    unique_count = sum(1 for it in real_build.gear.values() if it.is_unique)
    assert unique_count > 0, "expected at least one unique on this build"


def test_build_has_paragon_boards(real_build) -> None:
    assert len(real_build.paragon_path) > 0


def test_source_urls_recorded(real_build) -> None:
    assert "guide" in real_build.source_urls
    assert "planner" in real_build.source_urls
    assert "vw1uz0be" in real_build.source_urls["planner"]
