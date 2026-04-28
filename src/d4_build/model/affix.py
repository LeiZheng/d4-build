"""Affix model: a single rolled stat on an item, paragon node, or aspect."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .enums import DamageBucket


class Affix(BaseModel):
    """A single stat contribution.

    `bucket` drives the damage explainer — it tells us which multiplicative
    bucket this affix's value flows into.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    value: float
    bucket: DamageBucket = DamageBucket.OTHER


class ItemAffix(BaseModel):
    """A rolled affix as it appears on a specific item (planner pool entry).

    Distinct from `Affix` (which carries the bucket classification used by the
    damage explainer). ItemAffix is a low-level structural record — what
    Maxroll's planner JSON literally encodes per item, plus a humanized label
    for the report.
    """

    model_config = ConfigDict(extra="forbid")

    nid: int  # Blizzard SNO ID
    key: str = ""  # raw d4data key, e.g. 'S04_LifePerHit'
    label: str = ""  # humanized label, e.g. 'Life Per Hit'
    value: float = 0.0
    source: str = "explicit"  # 'implicit' | 'explicit' | 'tempered'
    greater: bool = False
    upgrade: int = 0
