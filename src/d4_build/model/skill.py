"""Skill model + skill-tree allocation step."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    class_id: str
    name: str
    tags: set[str] = set()
    ranks: int = 1


class SkillTreeStep(BaseModel):
    """One milestone in the skill-tree allocation order.

    A single planner build typically has 5-7 named steps (e.g.,
    "Starting Skills" -> "Defensive Skills" -> ... -> "Final Passives").
    Each step is *cumulative*: by the end of step N you should have
    `total_points` allocated across the listed `nodes_active`.
    """

    model_config = ConfigDict(extra="forbid")
    order: int
    name: str
    nodes_active: int
    total_points: int
    points_added: int = 0
    node_ids: list[str] = []
    node_labels: list[str] = []  # parallel to node_ids; "" if unresolved


class SkillPointClick(BaseModel):
    """One concrete `click here at level X` instruction in the allocation order."""

    model_config = ConfigDict(extra="forbid")
    level: int  # character level when this point is spent
    point_number: int  # 1-based ordinal of this point across the whole tree
    node_id: str
    node_label: str = ""
    new_rank: int = 1
    step_name: str = ""  # which named milestone this click belongs to
    cumulative_total: int = 0

