"""Per-point marginal analysis: show how each click changes damage / EHP / sustain.

Walks the build's `skill_point_clicks` and computes:
  Δdamage[i] = damage(after click i) - damage(after click i-1)
  Δsurvive[i], Δsustain[i] similarly

Uses the same `compute_character_stats` formula engine as the optimizer; the
delta is a real readout of the formula's response to each rank/node added.
"""

from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, ConfigDict

from ..model import Build, CharacterStats, SkillPointClick
from .formula import compute_character_stats


class PointMarginal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    point_number: int
    level: int
    node_label: str
    node_id: str
    new_rank: int
    step_name: str

    delta_damage: float = 0.0
    delta_survive: float = 0.0
    delta_sustain: float = 0.0
    delta_composite: float = 0.0

    cumulative_damage: float = 0.0
    cumulative_survive: float = 0.0
    cumulative_composite: float = 0.0


def compute_marginals(build: Build) -> list[PointMarginal]:
    """For each click, compute the delta from the previous state."""
    if not build.skill_point_clicks:
        return []

    out: list[PointMarginal] = []
    prev = compute_character_stats(
        build.model_copy(update={"skill_point_clicks": []})
    )
    clicks = build.skill_point_clicks
    for i, c in enumerate(clicks, start=1):
        partial = build.model_copy(update={"skill_point_clicks": clicks[:i]})
        cur = compute_character_stats(partial)
        out.append(PointMarginal(
            point_number=c.point_number,
            level=c.level,
            node_label=c.node_label or f"node {c.node_id}",
            node_id=c.node_id,
            new_rank=c.new_rank,
            step_name=c.step_name,
            delta_damage=round(cur.damage_score - prev.damage_score, 2),
            delta_survive=round(cur.survive_score - prev.survive_score, 2),
            delta_sustain=round(cur.sustain_score - prev.sustain_score, 2),
            delta_composite=round(cur.composite_score - prev.composite_score, 2),
            cumulative_damage=round(cur.damage_score, 1),
            cumulative_survive=round(cur.survive_score, 1),
            cumulative_composite=round(cur.composite_score, 1),
        ))
        prev = cur
    return out
