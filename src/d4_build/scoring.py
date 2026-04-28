"""Score a Maxroll planner variant on three axes (Damage / Survive / Sustain).

We deliberately use only signals derivable from the extracted PlannerVariant +
items pool — no fake formulas claiming in-game precision. The scores are 0-100
heuristic indices for *between-variant comparison within the same archetype*,
not absolute power numbers.

Inputs we use:
- variant.level (60 = endgame-eligible)
- variant.world_tier (1-8; 8 = Torment, full endgame)
- variant.items (slot count + the items_pool entries it references)
- items_pool[id].power (item power level — Mythic 925 > Ancestral 800 > Sacred 600)
- items_pool[id].id contains "_Unique_" -> uniques add per-axis bonuses
- items_pool[id].name presence -> legendary identification

Why these signals: they're the only structural info we have without pulling
affix-pool definitions from d4data, and they correlate well with overall
build power (more uniques + higher power + higher world tier = stronger).
"""

from __future__ import annotations

from .model import VariantScore
from .parsers.planner_remix import PlannerVariant


_BASELINE_POWER = 500.0  # Sacred-tier item power, lowest endgame-relevant.
_MAX_POWER = 925.0  # Mythic-tier reference.
_MAX_WORLD_TIER = 8.0


def _avg_item_power(variant: PlannerVariant, items_pool: dict[str, dict]) -> float:
    if not variant.items:
        return 0.0
    powers = []
    for _, item_id in variant.items.items():
        entry = items_pool.get(str(item_id), {})
        p = entry.get("power")
        if isinstance(p, (int, float)):
            powers.append(float(p))
    return sum(powers) / len(powers) if powers else 0.0


def _uniques_count(variant: PlannerVariant, items_pool: dict[str, dict]) -> int:
    count = 0
    for _, item_id in variant.items.items():
        entry = items_pool.get(str(item_id), {})
        if "_Unique_" in entry.get("id", ""):
            count += 1
    return count


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def score_variant(
    variant: PlannerVariant, items_pool: dict[str, dict]
) -> VariantScore:
    slots_filled = len(variant.items)
    uniques_count = _uniques_count(variant, items_pool)
    avg_power = _avg_item_power(variant, items_pool)
    level = variant.level
    world_tier = variant.world_tier

    # When a variant has no gear (e.g. "Skill Progression"), zero out the
    # score axes; otherwise the level/tier alone would mislead the comparison.
    if slots_filled == 0:
        return VariantScore(
            name=variant.name,
            level=level,
            world_tier=world_tier,
            slots_filled=0,
            uniques_count=0,
            avg_item_power=0.0,
            damage=0.0,
            survive=0.0,
            sustain=0.0,
            composite=0.0,
            notes="no gear — skill-tree reference variant",
        )

    # Normalize sub-signals to 0..1 then map to 0..100 with axis-specific weights.
    power_norm = _clip(
        (avg_power - _BASELINE_POWER) / (_MAX_POWER - _BASELINE_POWER), 0, 1
    )
    tier_norm = _clip(world_tier / _MAX_WORLD_TIER, 0, 1)
    slot_norm = _clip(slots_filled / 13.0, 0, 1)
    unique_factor = 1.0 + 0.10 * uniques_count  # 1.0..1.6 typical

    damage = _clip(
        100.0 * (0.45 * power_norm + 0.35 * tier_norm + 0.20 * slot_norm) * (
            unique_factor / 1.6
        )
        + 5.0 * uniques_count
    )
    survive = _clip(
        100.0 * (0.20 * power_norm + 0.40 * tier_norm + 0.40 * slot_norm)
        + 2.5 * uniques_count
    )
    sustain = _clip(
        100.0 * (0.15 * power_norm + 0.30 * tier_norm + 0.55 * slot_norm)
        + 1.5 * uniques_count
    )
    composite = round(0.5 * damage + 0.3 * survive + 0.2 * sustain, 1)

    return VariantScore(
        name=variant.name,
        level=level,
        world_tier=world_tier,
        slots_filled=slots_filled,
        uniques_count=uniques_count,
        avg_item_power=round(avg_power, 0),
        damage=round(damage, 1),
        survive=round(survive, 1),
        sustain=round(sustain, 1),
        composite=composite,
    )


def score_all_variants(
    variants: list[PlannerVariant], items_pool: dict[str, dict]
) -> list[VariantScore]:
    return [score_variant(v, items_pool) for v in variants]


def best_variant_name(scores: list[VariantScore]) -> str:
    if not scores:
        return ""
    return max(scores, key=lambda s: s.composite).name
