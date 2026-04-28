"""GameClass model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GameClass(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    slug: str
