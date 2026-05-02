"""Final-state character stats computed by walking the formulas.

These are heuristic proxies. They use the structural data we have (per-slot
affix counts and bucket categorization, paragon node counts, item power and
greater-affix counts, world tier, level) and the formulas in CLAUDE.md
section "G. Tool-implementation formulas".

Honest about what they aren't:
- Not in-game damage numbers. Real damage needs per-skill base coefficients
  + tag synergies + the complete multiplicative-bucket rollup.
- Not a replacement for the in-game training-dummy verification step.
- Not comparable across archetypes (each archetype's bucket weights differ).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CharacterStats(BaseModel):
    """Final computed character stats for one Build state.

    All numbers are heuristic 0-1000 indices except where labelled.
    """

    model_config = ConfigDict(extra="forbid")

    # Damage axis
    additive_damage_total: float = 0.0  # cumulative +X% additive damage
    vulnerable_multiplier: float = 1.20  # base 20%, scaled up by affixes
    crit_multiplier: float = 1.50  # base 50%
    overpower_multiplier: float = 1.0  # base 1.0; rolls based
    skill_tag_multiplier: float = 1.0  # product of all skill-tag [x]
    conditional_multiplier: float = 1.0  # product of all conditionals
    representative_damage: float = 0.0  # cumulative output of the formula

    # Survivability axis
    life_total: float = 0.0
    armor_total: float = 0.0
    damage_reduction_pct: float = 0.0  # composite DR after stacking
    effective_hp: float = 0.0  # life × DR_factor × armor_factor

    # Sustain axis
    cooldown_reduction_pct: float = 0.0
    resource_generation_pct: float = 0.0
    lucky_hit_pct: float = 0.0
    sustained_dps_factor: float = 1.0  # CDR + resource gen composite

    # Score breakdown (0-100)
    damage_score: float = 0.0
    survive_score: float = 0.0
    sustain_score: float = 0.0
    composite_score: float = 0.0


class OptimizerCandidate(BaseModel):
    """One trial point-allocation sequence and its score."""

    model_config = ConfigDict(extra="forbid")
    name: str
    description: str = ""
    point_count: int
    stats: CharacterStats
    delta_vs_baseline: float = 0.0  # composite_score - baseline composite


class OptimizerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gear_tier: str
    total_points: int
    baseline_name: str
    baseline_stats: CharacterStats
    candidates: list[OptimizerCandidate] = []
    best_name: str = ""
    best_delta: float = 0.0
    notes: str = ""
