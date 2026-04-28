"""Item model: a piece of equipment in a build."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .affix import Affix, ItemAffix
from .enums import GearSlot


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: GearSlot
    name: str
    is_unique: bool = False
    affixes: list[Affix] = []
    tempering: list[str] = []
    masterwork_priority: list[str] = []

    # Duplication-detail fields populated from the planner pool entry.
    pool_id: str = ""
    power: int = 0
    upgrade: int = 0
    implicits: list[ItemAffix] = []
    explicits: list[ItemAffix] = []
    tempered: list[ItemAffix] = []
    aspect_id: str = ""
    aspect_name: str = ""
    socket_count: int = 0
    sockets: list[str] = []
    greater_affix_count: int = 0
    suggested_affixes: list[str] = []
