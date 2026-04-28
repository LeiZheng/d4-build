"""Parse the Maxroll D4 planner page.

A planner page looks like:

    <html>...
    <script>window.__remixContext = {...big JSON...};</script>
    ...

The blob contains:
    state.loaderData["d4planner-by-id"].profile  — outer profile metadata
    state.loaderData["d4planner-by-id"].profile.data  — JSON-encoded string with
        the actual structured build (variants, items, skills, paragon).

This module is the only place that knows that shape. Downstream code consumes
the typed `PlannerProfileData` instead of raw dicts.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlannerVariant(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""
    level: int = 0
    world_tier: int = Field(default=0, alias="worldTier")
    items: dict[str, int] = {}
    skill_bar: list[str] = Field(default_factory=list, alias="skillBar")
    enchants: list[str] = []
    paragon: dict[str, Any] = {}
    skill_tree: dict[str, Any] = Field(default_factory=dict, alias="skillTree")


class PlannerProfileData(BaseModel):
    """The shape we care about from a Maxroll planner page."""

    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    class_name: str
    season: str = ""
    item_names: list[str] = []
    skill_names: list[str] = []
    specialization_names: list[str] = []
    variants: list[PlannerVariant] = []
    items_pool: dict[str, dict[str, Any]] = {}


def extract_remix_context(html: str) -> dict[str, Any]:
    """Extract the `window.__remixContext = { ... };` JSON object."""
    needle = "__remixContext"
    i = html.find(needle)
    if i < 0:
        raise ValueError("no __remixContext blob found on page")
    start = html.find("{", i)
    if start < 0:
        raise ValueError("__remixContext present but no opening brace")
    depth = 0
    in_string = False
    escape = False
    end = -1
    for j in range(start, len(html)):
        c = html[j]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end < 0:
        raise ValueError("__remixContext blob did not close cleanly")
    return json.loads(html[start:end])


def parse_planner_html(html: str) -> PlannerProfileData:
    ctx = extract_remix_context(html)
    route_data = ctx["state"]["loaderData"].get("d4planner-by-id")
    if not route_data:
        raise ValueError("planner page lacks d4planner-by-id loader data")
    profile = route_data["profile"]
    raw_data_str = profile.get("data") or "{}"
    inner = json.loads(raw_data_str)

    search = profile.get("search_metadata") or {}
    variants_raw = inner.get("profiles", []) or []
    variants = [PlannerVariant.model_validate(v) for v in variants_raw]

    return PlannerProfileData(
        id=profile.get("id", ""),
        name=profile.get("name", ""),
        class_name=profile.get("class", ""),
        season=profile.get("season", "") or "",
        item_names=list(search.get("items", []) or []),
        skill_names=list(search.get("skills", []) or []),
        specialization_names=list(search.get("specializations", []) or []),
        variants=variants,
        items_pool={str(k): v for k, v in (inner.get("items") or {}).items()},
    )
