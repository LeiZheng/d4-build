"""Paragon model: boards, nodes, glyphs, allocation steps."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .affix import Affix


class ParagonNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    affixes: list[Affix] = []


class Glyph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    rank: int = 1
    placement_order: int = 0


class ParagonBoard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    nodes: list[ParagonNode] = []
    glyphs: list[Glyph] = []
    placement_order: int = 0


class ParagonBoardSnapshot(BaseModel):
    """Per-step record of which nodes are active on one board."""

    model_config = ConfigDict(extra="forbid")
    board_id: str
    board_name: str
    node_count: int
    node_ids: list[str] = []
    glyph_id: str = ""
    glyph_name: str = ""
    glyph_rank: int = 0
    rotation: int = 0  # board orientation 0/1/2/3 = N/E/S/W


class ParagonStep(BaseModel):
    """A named milestone in the paragon progression (e.g., 'Board Rush', 'Endgame').

    Each step lists the boards activated at that point along with how many
    nodes are allocated on each.
    """

    model_config = ConfigDict(extra="forbid")
    order: int
    name: str
    boards: list[ParagonBoardSnapshot] = []
    total_points: int = 0
