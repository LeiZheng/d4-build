"""Build, BuildSummary, DamageBreakdown — the central report model.

Build is what `d4-build show <id>` renders into Markdown.
BuildSummary is what `d4-build <class>` lists in a table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .class_ import GameClass
from .enums import DamageBucket, GearSlot
from .item import Item
from .paragon import ParagonBoard, ParagonStep
from .skill import Skill, SkillTreeStep


class StatPriority(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    target: str
    notes: str = ""


class VariantScore(BaseModel):
    """Scored axes for one named planner variant (Mythic, Ancestral, Starter, ...).

    Scores are 0-100 heuristic indices, NOT in-game numbers. They use signals
    we can extract from the planner JSON (item power, world tier, uniques
    count, gear slots filled). Use them to compare *between variants of the
    same archetype*; absolute values across archetypes aren't directly
    comparable.
    """

    model_config = ConfigDict(extra="forbid")
    name: str
    level: int
    world_tier: int
    slots_filled: int
    uniques_count: int
    avg_item_power: float
    damage: float
    survive: float
    sustain: float
    composite: float
    notes: str = ""


class Build(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    class_: GameClass = Field(alias="class")
    archetype: str
    tier: str
    role: str
    skills_in_order: list[Skill] = []
    skill_tree_steps: list[SkillTreeStep] = []
    enchants: list[str] = []
    gear: dict[GearSlot, Item] = {}
    paragon_path: list[ParagonBoard] = []
    paragon_steps: list[ParagonStep] = []
    variant_scores: list[VariantScore] = []
    chosen_variant: str = ""
    stat_priorities: list[StatPriority] = []
    season: str = ""
    source_urls: dict[str, str] = {}
    planner_id: str = ""
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rotation_prose: str = ""
    conflicts: list[dict[str, Any]] = []


class BuildSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    class_id: str
    archetype: str
    tier: str
    role: str
    url: str


class BucketContribution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bucket: DamageBucket
    additive_total: float = 0.0
    multiplier_total: float = 1.0
    contribution_pct: float = 0.0
    contributors: list[str] = []


class DamageBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")
    per_bucket: list[BucketContribution]
    dominant_bucket: DamageBucket
    explanation_prose: str = ""
