"""Compare two skill-point allocations side by side.

Used to benchmark our greedy optimizer against Maxroll's published plan
and to track convergence as we tune constraints.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from ..model import SkillPointClick


class PlanDiff(BaseModel):
    """Difference between two plans for one specific node."""

    model_config = ConfigDict(extra="forbid")
    node_id: str
    label: str = ""
    rank_a: int = 0
    rank_b: int = 0


class PlanComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_a: str
    name_b: str
    points_a: int
    points_b: int
    nodes_a: int
    nodes_b: int

    shared_nodes: list[PlanDiff] = []
    only_a: list[PlanDiff] = []
    only_b: list[PlanDiff] = []

    jaccard_node_set: float = 0.0  # |A∩B| / |A∪B| over node ids
    rank_l1: int = 0  # sum of |rank_a - rank_b| across all nodes
    notes: str = ""


def _state_from(plan: list[SkillPointClick]) -> dict[str, tuple[str, int]]:
    """Roll a plan into final-state ranks: node_id -> (label, rank)."""
    state: dict[str, tuple[str, int]] = {}
    for c in plan:
        prev_label, _ = state.get(c.node_id, (c.node_label, 0))
        state[c.node_id] = (c.node_label or prev_label, max(c.new_rank, state.get(c.node_id, ("", 0))[1]))
    return state


def compare_plans(
    plan_a: list[SkillPointClick],
    plan_b: list[SkillPointClick],
    *,
    name_a: str = "A",
    name_b: str = "B",
) -> PlanComparison:
    sa = _state_from(plan_a)
    sb = _state_from(plan_b)
    keys_a = set(sa.keys())
    keys_b = set(sb.keys())

    shared = sorted(keys_a & keys_b, key=lambda k: int(k))
    only_a = sorted(keys_a - keys_b, key=lambda k: int(k))
    only_b = sorted(keys_b - keys_a, key=lambda k: int(k))

    shared_diffs = [
        PlanDiff(
            node_id=k,
            label=sa[k][0] or sb[k][0],
            rank_a=sa[k][1],
            rank_b=sb[k][1],
        )
        for k in shared
    ]
    only_a_diffs = [
        PlanDiff(node_id=k, label=sa[k][0], rank_a=sa[k][1], rank_b=0)
        for k in only_a
    ]
    only_b_diffs = [
        PlanDiff(node_id=k, label=sb[k][0], rank_a=0, rank_b=sb[k][1])
        for k in only_b
    ]

    union = keys_a | keys_b
    jaccard = (len(keys_a & keys_b) / len(union)) if union else 0.0
    rank_l1 = (
        sum(abs(d.rank_a - d.rank_b) for d in shared_diffs)
        + sum(d.rank_a for d in only_a_diffs)
        + sum(d.rank_b for d in only_b_diffs)
    )

    return PlanComparison(
        name_a=name_a,
        name_b=name_b,
        points_a=sum(c.new_rank for c in plan_a if c.new_rank > 0),  # rough
        points_b=sum(c.new_rank for c in plan_b if c.new_rank > 0),
        nodes_a=len(keys_a),
        nodes_b=len(keys_b),
        shared_nodes=shared_diffs,
        only_a=only_a_diffs,
        only_b=only_b_diffs,
        jaccard_node_set=round(jaccard, 3),
        rank_l1=rank_l1,
    )
