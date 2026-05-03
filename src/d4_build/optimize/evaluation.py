"""Parameterized evaluation system for skill-allocation plans.

Game-knowledge-driven scoring with tunable weights. The weights are
calibrated against Maxroll's published build plans as training data
(see training.py).

Design:
- A plan is a list of SkillPointClick.
- evaluate(plan, build, weights) -> float (higher is better)
- The score combines:
    1. Damage component: rank-up scaling + skill-tag synergy
    2. Survival component: defensive node count + EHP from gear
    3. Sustain component: CDR + resource gen
    4. Viability (hard constraint): Basic + Core + Defensive presence
    5. Synergy bonus: skill tags from build's primary skill matched in nodes
    6. Diversity penalty: too many points on one node above its natural cap

Each weight in `EvaluationWeights` is a tunable knob. Defaults are set to
match D4 game-knowledge first, then refined against Maxroll training data.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from ..model import Build, SkillPointClick
from .formula import compute_character_stats


class EvaluationWeights(BaseModel):
    """Tunable weights for the plan evaluator."""

    model_config = ConfigDict(extra="forbid")

    # Component weights for the composite score.
    w_damage: float = 0.50
    w_survive: float = 0.30
    w_sustain: float = 0.20

    # Game-knowledge weights — tunable.
    rank_value_basic: float = 0.30      # Basic skill rank-up = +30% utility per rank
    rank_value_core: float = 1.00       # Core rank-up = full damage bucket
    rank_value_defensive: float = 0.20
    rank_value_other: float = 0.10

    # Modifier (Upgrade2/3/4/A/B/C) values — flat unlock contributions.
    enhanced_value: float = 0.50        # Upgrade1 (Enhanced)
    spec_value: float = 0.40            # Upgrade2/3/4 (Specialization Mods)
    higher_passive_value: float = 0.30  # UpgradeA/B/C (higher-tier passives)

    # Hard-constraint penalties.
    no_basic_penalty: float = 50.0
    no_core_penalty: float = 100.0
    no_defensive_penalty: float = 30.0

    # Diversity: penalize when a single node has more than this many ranks.
    excess_rank_threshold: int = 5
    excess_rank_penalty: float = 5.0

    # Synergy bonus when a node's cluster matches the primary archetype tag.
    matched_cluster_bonus: float = 0.50


def _classify_click(click: SkillPointClick) -> tuple[str, str]:
    """Return (cluster_kind, click_kind) classification for a click."""
    label = click.node_label or ""
    cluster = ""
    # 1. Old humanized form: "Demon (Core)" — has the cluster in parens.
    for kw in ("Basic", "Core", "Defensive", "Sigil", "Archfiend",
               "Mastery", "Ultimate", "Capstone", "Special"):
        if f"({kw})" in label:
            cluster = kw
            break

    # 2. New mapped form: "Dread Claws — Cascading Dread" — look up via
    # the display_name-to-cluster table.
    if not cluster:
        from ..skill_modifier_mapping import display_name_to_cluster
        # Strip Enhanced prefix and Mod-name suffix to get the bare skill name.
        base = label
        if base.startswith("Enhanced "):
            base = base[len("Enhanced "):]
        if " — " in base:
            base = base.split(" — ")[0]
        cluster = display_name_to_cluster().get(base.strip(), "")

    # Click kind: rank-up, enhanced, spec, or base
    kind = "base"
    if click.new_rank > 1:
        kind = "rank_up"
    elif label.startswith("Enhanced "):
        kind = "enhanced"
    elif " — " in label:
        kind = "spec"
    return cluster, kind


def _per_node_rank(plan: list[SkillPointClick]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in plan:
        out[c.node_id] = max(out.get(c.node_id, 0), c.new_rank)
    return out


def evaluate(
    plan: list[SkillPointClick],
    build: Build,
    weights: EvaluationWeights | None = None,
) -> float:
    """Score a plan; higher = better."""
    w = weights or EvaluationWeights()
    if not plan:
        return -w.no_basic_penalty - w.no_core_penalty - w.no_defensive_penalty

    score = 0.0
    cluster_points: dict[str, int] = defaultdict(int)

    for c in plan:
        cluster, kind = _classify_click(c)
        cluster_points[cluster] += 1

        if kind == "rank_up":
            if cluster == "Basic":
                score += w.rank_value_basic
            elif cluster == "Core":
                score += w.rank_value_core
            elif cluster == "Defensive":
                score += w.rank_value_defensive
            else:
                score += w.rank_value_other
        elif kind == "enhanced":
            score += w.enhanced_value
        elif kind == "spec":
            score += w.spec_value
        elif kind == "base":
            # Taking a base node is the cluster-unlock; small but real.
            score += 0.20

    # Hard-constraint penalties.
    if cluster_points["Basic"] == 0:
        score -= w.no_basic_penalty
    if cluster_points["Core"] == 0:
        score -= w.no_core_penalty
    if cluster_points["Defensive"] == 0:
        score -= w.no_defensive_penalty

    # Diversity penalty.
    ranks = _per_node_rank(plan)
    for nid, rank in ranks.items():
        if rank > w.excess_rank_threshold:
            score -= (rank - w.excess_rank_threshold) * w.excess_rank_penalty

    # Cluster diversity bonus — having Basic + Core + Defensive + at least one
    # of (Sigil / Archfiend / Mastery) signals a complete build.
    distinct_clusters = sum(
        1 for k in ("Basic", "Core", "Defensive", "Sigil", "Archfiend", "Mastery")
        if cluster_points.get(k, 0) > 0
    )
    score += distinct_clusters * 1.0

    # Layer in the gear-stat composite from formula.py — this carries the
    # affix bucket math through items + paragon.
    partial_build = build.model_copy(update={"skill_point_clicks": plan})
    stats = compute_character_stats(partial_build)
    score += (
        w.w_damage * stats.damage_score
        + w.w_survive * stats.survive_score
        + w.w_sustain * stats.sustain_score
    )

    return round(score, 3)


def evaluate_with_breakdown(
    plan: list[SkillPointClick],
    build: Build,
    weights: EvaluationWeights | None = None,
) -> dict[str, float]:
    """Return per-component scores for diagnostic purposes."""
    w = weights or EvaluationWeights()
    breakdown: dict[str, float] = {
        "rank_ups": 0.0,
        "enhanced": 0.0,
        "spec": 0.0,
        "base": 0.0,
        "viability_penalty": 0.0,
        "diversity_penalty": 0.0,
        "cluster_bonus": 0.0,
        "gear_damage": 0.0,
        "gear_survive": 0.0,
        "gear_sustain": 0.0,
    }
    cluster_points: dict[str, int] = defaultdict(int)
    for c in plan:
        cluster, kind = _classify_click(c)
        cluster_points[cluster] += 1
        if kind == "rank_up":
            v = {"Basic": w.rank_value_basic, "Core": w.rank_value_core,
                 "Defensive": w.rank_value_defensive}.get(cluster, w.rank_value_other)
            breakdown["rank_ups"] += v
        elif kind == "enhanced":
            breakdown["enhanced"] += w.enhanced_value
        elif kind == "spec":
            breakdown["spec"] += w.spec_value
        elif kind == "base":
            breakdown["base"] += 0.20

    if cluster_points["Basic"] == 0:
        breakdown["viability_penalty"] -= w.no_basic_penalty
    if cluster_points["Core"] == 0:
        breakdown["viability_penalty"] -= w.no_core_penalty
    if cluster_points["Defensive"] == 0:
        breakdown["viability_penalty"] -= w.no_defensive_penalty

    ranks = _per_node_rank(plan)
    for nid, rank in ranks.items():
        if rank > w.excess_rank_threshold:
            breakdown["diversity_penalty"] -= (rank - w.excess_rank_threshold) * w.excess_rank_penalty

    distinct_clusters = sum(
        1 for k in ("Basic", "Core", "Defensive", "Sigil", "Archfiend", "Mastery")
        if cluster_points.get(k, 0) > 0
    )
    breakdown["cluster_bonus"] = distinct_clusters * 1.0

    partial_build = build.model_copy(update={"skill_point_clicks": plan})
    stats = compute_character_stats(partial_build)
    breakdown["gear_damage"] = w.w_damage * stats.damage_score
    breakdown["gear_survive"] = w.w_survive * stats.survive_score
    breakdown["gear_sustain"] = w.w_sustain * stats.sustain_score

    breakdown["TOTAL"] = round(sum(breakdown.values()), 3)
    return breakdown
