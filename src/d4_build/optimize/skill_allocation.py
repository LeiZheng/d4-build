"""Heuristic optimizer for skill-point allocation.

Strategy:
1. Take Maxroll's recommended click sequence as the baseline.
2. Generate N perturbations: front-load Core ranks, front-load Defensive,
   delay Sigil, etc. — each perturbation is a permutation of the same set
   of clicks (same final tree state, different intermediate states).
3. For each perturbation, compute CharacterStats at the user's target
   point count (truncate the sequence).
4. Pick the highest composite score for the requested gear tier.

Honesty:
- The optimizer compares **intermediate states** of the Maxroll-built tree.
  It can't invent a *different* end-state tree (that's the deferred Option γ
  combinatorial search through 270 nodes).
- The bucket classifier is keyword-based; bucket assignments may be off
  in ways the score papers over.
- Gear-tier modifiers boost expected affix values per tier; they don't
  change the underlying point sequence Maxroll prescribed.

Use the result as a *suggestion*, not a guarantee.
"""

from __future__ import annotations

from copy import deepcopy

from ..model import (
    Build,
    CharacterStats,
    OptimizerCandidate,
    OptimizerResult,
    SkillPointClick,
)
from .formula import compute_character_stats


# Per-gear-tier expected affix-value multiplier.
# Calibrated so Sacred (500) -> baseline, Mythic (925) -> ~2x.
_TIER_VALUE_MULT = {
    "sacred": 1.00,    # 500 power
    "ancestral": 1.40, # 800 power
    "legendary": 1.55, # 875 power
    "mythic": 1.80,    # 925 power
}


def _truncate_clicks(build: Build, n: int) -> Build:
    return build.model_copy(update={
        "skill_point_clicks": build.skill_point_clicks[:n],
    })


def _scale_build_to_tier(build: Build, tier: str) -> Build:
    """Return a copy of build with item affix values scaled by gear tier."""
    mult = _TIER_VALUE_MULT.get(tier.lower(), 1.0)
    if mult == 1.0:
        return build
    new_gear = {}
    for slot, item in build.gear.items():
        item_copy = item.model_copy(deep=True)
        for collection in (item_copy.implicits, item_copy.explicits, item_copy.tempered):
            for a in collection:
                a.value = a.value * mult
        new_gear[slot] = item_copy
    return build.model_copy(update={"gear": new_gear})


def _front_load_core(clicks: list[SkillPointClick]) -> list[SkillPointClick]:
    """Take rank-up clicks (new_rank > 1) and move them earlier within their step."""
    by_step: dict[str, list[SkillPointClick]] = {}
    for c in clicks:
        by_step.setdefault(c.step_name, []).append(c)
    out: list[SkillPointClick] = []
    for step_name, items in by_step.items():
        rank_ups = [c for c in items if c.new_rank > 1]
        new_takes = [c for c in items if c.new_rank == 1]
        # Keep new takes first within the step (you usually can't rank up a
        # node before unlocking it), then rank-ups packed at the end.
        out.extend(new_takes + rank_ups)
    # Renumber points + re-stamp levels in original order.
    for i, c in enumerate(out, start=1):
        c.point_number = i
    return out


def _front_load_defensive(clicks: list[SkillPointClick]) -> list[SkillPointClick]:
    """Pull defensive nodes earlier — useful when low-tier gear means low EHP."""
    def is_defensive(c: SkillPointClick) -> bool:
        lbl = (c.node_label or "").lower()
        return "defensive" in lbl or "defense" in lbl
    early = [c for c in clicks if is_defensive(c)]
    rest = [c for c in clicks if not is_defensive(c)]
    out = early + rest
    for i, c in enumerate(out, start=1):
        c.point_number = i
    return out


def _conservative_first(clicks: list[SkillPointClick]) -> list[SkillPointClick]:
    """Order: defensive → basic → core → sigil → archfiend → other."""
    def priority(c: SkillPointClick) -> int:
        lbl = (c.node_label or "").lower()
        if "defensive" in lbl: return 0
        if "(basic)" in lbl: return 1
        if "(core)" in lbl: return 2
        if "(sigil)" in lbl: return 3
        if "(archfiend)" in lbl: return 4
        return 5
    out = sorted(clicks, key=priority)
    for i, c in enumerate(out, start=1):
        c.point_number = i
    return out


def optimize(
    build: Build,
    *,
    gear_tier: str = "ancestral",
    total_points: int = 40,
) -> OptimizerResult:
    """Run the heuristic optimizer; return baseline + ranked candidates."""
    if not build.skill_point_clicks:
        return OptimizerResult(
            gear_tier=gear_tier,
            total_points=total_points,
            baseline_name="(no Maxroll click sequence available)",
            baseline_stats=CharacterStats(),
            notes="Build had no skill_point_clicks data; optimizer cannot run.",
        )

    scaled = _scale_build_to_tier(build, gear_tier)
    base_clicks = list(scaled.skill_point_clicks)

    candidates: list[tuple[str, str, list[SkillPointClick]]] = [
        ("Maxroll baseline", "Maxroll's published sequence, sliced to target.", base_clicks),
        ("Front-load Core ranks", "Same final tree; rank-up clicks pulled earlier within each step.", _front_load_core(deepcopy(base_clicks))),
        ("Front-load Defensive", "Defensive cluster earlier — better EHP at low gear tiers.", _front_load_defensive(deepcopy(base_clicks))),
        ("Conservative tier order", "Defensive → Basic → Core → Sigil → Archfiend across the whole sequence.", _conservative_first(deepcopy(base_clicks))),
    ]

    # Compute baseline stats first.
    baseline_build = scaled.model_copy(update={
        "skill_point_clicks": base_clicks[:total_points],
    })
    baseline_stats = compute_character_stats(baseline_build)

    # Score every candidate.
    out: list[OptimizerCandidate] = []
    for name, desc, clicks in candidates:
        cand_build = scaled.model_copy(update={
            "skill_point_clicks": clicks[:total_points],
        })
        s = compute_character_stats(cand_build)
        delta = s.composite_score - baseline_stats.composite_score
        out.append(OptimizerCandidate(
            name=name,
            description=desc,
            point_count=min(total_points, len(clicks)),
            stats=s,
            delta_vs_baseline=round(delta, 2),
        ))

    # Pick the best.
    best = max(out, key=lambda c: c.stats.composite_score)

    return OptimizerResult(
        gear_tier=gear_tier,
        total_points=total_points,
        baseline_name="Maxroll baseline",
        baseline_stats=baseline_stats,
        candidates=out,
        best_name=best.name,
        best_delta=round(best.stats.composite_score - baseline_stats.composite_score, 2),
        notes=(
            f"Optimizer compared {len(out)} candidate sequences over the same "
            f"final tree state. Heuristic only — actual in-game ranking may "
            f"differ. Run `d4-build show ... --points {total_points}` to see "
            f"the chosen baseline allocation."
        ),
    )
