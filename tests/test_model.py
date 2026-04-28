"""Tests for the core Pydantic data model.

We test the model is the single source of truth for build shape:
- A Build has a class, archetype, skills, gear, paragon, stat priorities
- An Affix has a damage bucket (drives the explainer)
- BuildSummary is what `d4-build <class>` lists
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from d4_build.model import (
    Affix,
    Build,
    BuildSummary,
    DamageBucket,
    GameClass,
    GearSlot,
    Item,
    Skill,
)


def test_damage_bucket_enum_covers_d4_buckets():
    assert DamageBucket.ADDITIVE in DamageBucket
    assert DamageBucket.VULNERABLE in DamageBucket
    assert DamageBucket.CRIT in DamageBucket
    assert DamageBucket.OVERPOWER in DamageBucket
    assert DamageBucket.SKILL_TAG in DamageBucket
    assert DamageBucket.OTHER in DamageBucket


def test_affix_round_trip():
    a = Affix(key="vulnerable_damage", value=18.5, bucket=DamageBucket.VULNERABLE)
    assert a.key == "vulnerable_damage"
    assert a.value == 18.5
    assert a.bucket == DamageBucket.VULNERABLE


def test_affix_value_must_be_numeric():
    with pytest.raises(ValidationError):
        Affix(key="x", value="not a number", bucket=DamageBucket.ADDITIVE)  # type: ignore[arg-type]


def test_item_with_unique_flag():
    boots = Item(
        slot=GearSlot.BOOTS,
        name="Wildbolt Runic Cleats",
        is_unique=True,
        affixes=[Affix(key="movement_speed", value=20, bucket=DamageBucket.OTHER)],
    )
    assert boots.is_unique
    assert boots.slot == GearSlot.BOOTS
    assert len(boots.affixes) == 1


def test_skill_with_tags():
    s = Skill(
        id=291403,
        class_id="sorcerer",
        name="Blizzard",
        tags={"cold", "conjuration", "core"},
        ranks=3,
    )
    assert "cold" in s.tags
    assert s.ranks == 3


def test_build_minimal_construction():
    """A Build can be constructed with the minimum set of fields a report needs."""
    b = Build(
        id="vw1uz0be",
        class_=GameClass(id="sorcerer", name="Sorcerer", slug="sorcerer"),
        archetype="Blizzard",
        tier="S",
        role="endgame",
        skills_in_order=[
            Skill(id=287256, class_id="sorcerer", name="Frost Bolt", tags=set(), ranks=1),
            Skill(id=291403, class_id="sorcerer", name="Blizzard", tags=set(), ranks=3),
        ],
        gear={},
        paragon_path=[],
        stat_priorities=[],
        season="Season 12",
        source_urls={"guide": "https://maxroll.gg/d4/build-guides/blizzard-sorcerer-guide"},
        planner_id="vw1uz0be",
    )
    assert b.archetype == "Blizzard"
    assert len(b.skills_in_order) == 2
    assert b.skills_in_order[1].name == "Blizzard"


def test_build_summary_for_listing():
    """BuildSummary is what d4-build <class> renders in the table."""
    s = BuildSummary(
        id="vw1uz0be",
        class_id="sorcerer",
        archetype="Blizzard",
        tier="S",
        role="endgame",
        url="https://maxroll.gg/d4/build-guides/blizzard-sorcerer-guide",
    )
    assert s.tier == "S"


def test_gear_slot_enum_covers_thirteen_d4_slots():
    """D4 has exactly 13 equipment slots."""
    assert len(list(GearSlot)) == 13
