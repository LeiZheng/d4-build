"""Greedy hill-climb optimizer over the full SkillKit.

Genuine combinatorial enumeration of C(270, 40) = ~10^48 sequences is
infeasible. This is a greedy hill-climb: at each step we evaluate every
gate-legal next node, pick the one with highest marginal composite gain,
and continue until the budget is spent.

Honesty:
- Greedy is not globally optimal — it can land in a local optimum that
  "ranking up Core 2 more times" beats taking a Defensive node, even though
  the global best might require a defensive setup first.
- Gate-validation is *approximate*: we check `dwNodeRequiredPlayerLevel`
  and tier-of-cluster (using node-name keywords) but not full prerequisite
  chains via `arConnections` — that would be another half-day of work.
- The score function is heuristic (see formula.py).
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..model import Build, CharacterStats, SkillPointClick
from ..sources.d4data import D4DataLookup, _humanize_skill_gbid
from .formula import compute_character_stats


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total_points: int
    final_stats: CharacterStats
    plan: list[SkillPointClick] = []
    notes: str = ""


# Cluster name → required tier (number of points spent before unlocking).
_CLUSTER_TIER_REQUIREMENT = {
    "Basic": 0,
    "Core": 0,
    "Defensive": 5,
    "Sigil": 10,
    "Mastery": 15,
    "Archfiend": 15,
    "Ultimate": 25,
    "Capstone": 30,
}


def _node_cluster(label: str) -> str:
    """Extract cluster name from `Demon (Core)` -> 'Core'."""
    if "(" in label and ")" in label:
        return label.split("(")[-1].rstrip(")").strip()
    return ""


def _is_node_legal(
    node_id: str,
    label: str,
    current_state: dict[str, int],
    current_level: int,
    node_required_levels: dict[str, int],
) -> bool:
    """Coarse legality check — level + tier-of-cluster requirements."""
    req_level = node_required_levels.get(node_id, 0)
    if req_level > current_level:
        return False
    cluster = _node_cluster(label)
    tier_req = _CLUSTER_TIER_REQUIREMENT.get(cluster, 0)
    if tier_req > sum(current_state.values()):
        return False
    return True


def greedy_search(
    build: Build,
    *,
    total_points: int = 40,
    class_slug: str = "warlock",
    max_rank_per_node: int = 5,
    d4data: D4DataLookup | None = None,
) -> SearchResult:
    """Greedy hill-climb. Returns a 40-step plan with stats."""
    lookup = d4data or D4DataLookup()
    if not lookup.is_available():
        return SearchResult(
            total_points=total_points,
            final_stats=CharacterStats(),
            notes="d4data not available — search needs the SkillKit to enumerate nodes.",
        )

    # Load every node from Warlock.skl.json
    sk_path = lookup.skill_kit_dir / f"{class_slug.title()}.skl.json"
    if not sk_path.exists():
        return SearchResult(
            total_points=total_points,
            final_stats=CharacterStats(),
            notes=f"SkillKit not found at {sk_path}.",
        )
    sk = json.loads(sk_path.read_text())
    raw_nodes = sk.get("arNodes", [])

    node_label: dict[str, str] = {}
    node_required_level: dict[str, int] = {}
    for n in raw_nodes:
        nid = n.get("dwID")
        if not isinstance(nid, int):
            continue
        gbid = n.get("gbidReward", {}) or {}
        gbid_name = gbid.get("name") if isinstance(gbid, dict) else ""
        node_label[str(nid)] = (
            _humanize_skill_gbid(gbid_name) if gbid_name else f"node {nid}"
        )
        node_required_level[str(nid)] = int(n.get("dwNodeRequiredPlayerLevel", 0))

    # Greedy loop
    state: dict[str, int] = {}  # node_id -> rank
    plan: list[SkillPointClick] = []

    for point_n in range(1, total_points + 1):
        # Roughly: each point is gained at level point_n + 1 (D4 starts at level 2).
        current_level = point_n + 1
        cumulative = sum(state.values())

        # Gate-legal candidates
        legal: list[tuple[str, str, int]] = []
        for nid_str, label in node_label.items():
            current_rank = state.get(nid_str, 0)
            if current_rank >= max_rank_per_node:
                continue
            if not _is_node_legal(
                nid_str, label, state, current_level, node_required_level
            ):
                continue
            legal.append((nid_str, label, current_rank + 1))

        if not legal:
            break

        # Score each candidate by simulating the click
        best_candidate = None
        best_delta = float("-inf")
        baseline_stats = compute_character_stats(
            build.model_copy(update={"skill_point_clicks": plan})
        )
        for nid_str, label, new_rank in legal:
            trial_click = SkillPointClick(
                level=current_level,
                point_number=point_n,
                node_id=nid_str,
                node_label=label,
                new_rank=new_rank,
                step_name="greedy",
                cumulative_total=cumulative + 1,
            )
            trial = build.model_copy(update={
                "skill_point_clicks": plan + [trial_click],
            })
            s = compute_character_stats(trial)
            delta = s.composite_score - baseline_stats.composite_score
            if delta > best_delta:
                best_delta = delta
                best_candidate = trial_click

        if best_candidate is None:
            break

        plan.append(best_candidate)
        state[best_candidate.node_id] = best_candidate.new_rank

    final_build = build.model_copy(update={"skill_point_clicks": plan})
    final_stats = compute_character_stats(final_build)
    return SearchResult(
        total_points=len(plan),
        final_stats=final_stats,
        plan=plan,
        notes=(
            f"Greedy hill-climb over {len(node_label)} nodes, gate-legal "
            f"candidates per step ranged from ~{len(legal) if legal else 0} "
            f"down. Heuristic — not globally optimal."
        ),
    )
