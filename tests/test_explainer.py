"""Damage-bucket explainer tests."""

from __future__ import annotations

from d4_build.explain.buckets import explain_damage
from d4_build.model import Build, DamageBucket, GameClass


def _stub_build(archetype: str) -> Build:
    return Build(
        id="stub",
        **{"class": GameClass(id="sorcerer", name="Sorcerer", slug="sorcerer")},
        archetype=archetype,
        tier="S",
        role="Endgame",
    )


def test_breakdown_has_all_buckets() -> None:
    breakdown = explain_damage(_stub_build("Blizzard"))
    buckets = {c.bucket for c in breakdown.per_bucket}
    assert DamageBucket.ADDITIVE in buckets
    assert DamageBucket.VULNERABLE in buckets
    assert DamageBucket.CRIT in buckets


def test_blizzard_dominant_bucket_is_vulnerable() -> None:
    breakdown = explain_damage(_stub_build("Blizzard"))
    assert breakdown.dominant_bucket == DamageBucket.VULNERABLE


def test_contributions_sum_to_100() -> None:
    breakdown = explain_damage(_stub_build("Hydra"))
    total = sum(c.contribution_pct for c in breakdown.per_bucket)
    assert 99.0 <= total <= 101.0  # rounding tolerance


def test_explanation_prose_mentions_dominant_bucket() -> None:
    breakdown = explain_damage(_stub_build("Blizzard"))
    assert "Vulnerable" in breakdown.explanation_prose
    assert "Crit is king" in breakdown.explanation_prose


def test_unknown_archetype_falls_back_safely() -> None:
    """Unknown archetype defaults to Vulnerable but still produces a valid breakdown."""
    breakdown = explain_damage(_stub_build("Some New Skill That Did Not Exist"))
    assert breakdown.dominant_bucket in DamageBucket
    assert breakdown.explanation_prose
