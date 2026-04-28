"""Variant scoring tests against the saved Blizzard Sorc planner fixture."""

from __future__ import annotations

import pytest

from d4_build.parsers.planner_remix import parse_planner_html
from d4_build.scoring import (
    best_variant_name,
    score_all_variants,
    score_variant,
)
from tests.conftest import require_maxroll_fixture


@pytest.fixture
def profile():
    return parse_planner_html(
        require_maxroll_fixture("planner-vw1uz0be.html").read_text()
    )


def test_each_variant_gets_a_score(profile) -> None:
    scores = score_all_variants(profile.variants, profile.items_pool)
    assert len(scores) == len(profile.variants)
    for s in scores:
        assert 0.0 <= s.damage <= 100.0
        assert 0.0 <= s.survive <= 100.0
        assert 0.0 <= s.sustain <= 100.0
        assert 0.0 <= s.composite <= 100.0


def test_mythic_outscores_leveling(profile) -> None:
    """Mythic has more uniques + higher world tier than Leveling -> higher composite."""
    by_name = {
        s.name: s
        for s in score_all_variants(profile.variants, profile.items_pool)
    }
    assert by_name["Mythic"].composite > by_name["Leveling"].composite


def test_mythic_outscores_ancestral_on_damage(profile) -> None:
    """Mythic has +1 unique and equal slot/power vs Ancestral."""
    by_name = {
        s.name: s
        for s in score_all_variants(profile.variants, profile.items_pool)
    }
    assert by_name["Mythic"].damage >= by_name["Ancestral"].damage


def test_skill_progression_variant_gets_zero_score(profile) -> None:
    """The 'Skill Progression' variant has no gear; its score is zeroed."""
    by_name = {
        s.name: s
        for s in score_all_variants(profile.variants, profile.items_pool)
    }
    sp = by_name.get("Skill Progression")
    assert sp is not None
    assert sp.composite == 0.0
    assert "no gear" in sp.notes


def test_best_variant_is_mythic(profile) -> None:
    scores = score_all_variants(profile.variants, profile.items_pool)
    assert best_variant_name(scores) == "Mythic"


def test_score_variant_records_metadata(profile) -> None:
    """Each score carries the readable signals it was computed from."""
    mythic = next(v for v in profile.variants if v.name == "Mythic")
    s = score_variant(mythic, profile.items_pool)
    assert s.slots_filled == len(mythic.items)
    assert s.world_tier == mythic.world_tier
    assert s.uniques_count >= 1
