from __future__ import annotations

import pytest

from d4_build.humanize import humanize_key


@pytest.mark.parametrize(
    "key,expected",
    [
        ("S04_LifePerHit", "Life Per Hit"),
        ("S04_Movement_Speed", "Movement Speed"),
        ("UBERUNIQUE_LifeFlat_HarlequinCrest", "Life Flat"),
        ("UBERUNIQUE_Resource_Max_AllClasses_HarlequinCrest", "Resource Max"),
        ("UNIQUE_INHERENT_PassiveRankBonus_Generic_All_ShroudOfFalseDeath", "Passive Rank Bonus"),
        ("Rune_Condition_HitHealthierEnemy", "Hit Healthier Enemy"),
        ("Resistance_Jewelry_All", "Resistance Jewelry"),
        ("UBERUNIQUE_CoreStat_Intelligence_Higher", "Core Stat Intelligence Higher"),
        ("UBERUNIQUE_INHERENT_PassiveRankBonus_Generic_All_HarlequinCrest", "Passive Rank Bonus"),
    ],
)
def test_humanize_key(key: str, expected: str) -> None:
    assert humanize_key(key) == expected


def test_empty_key_returns_empty() -> None:
    assert humanize_key("") == ""


def test_unknown_keys_round_trip_words() -> None:
    """Even with no prefix match, CamelCase → spaced words."""
    assert humanize_key("WeirdNewKey") == "Weird New Key"
