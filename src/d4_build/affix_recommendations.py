"""Loader for hand-curated per-slot affix-priority recommendations."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .model import GearSlot


_DATA_PATH = Path(__file__).parent / "data" / "affix_recommendations.yaml"


@lru_cache(maxsize=1)
def _load() -> dict:
    return yaml.safe_load(_DATA_PATH.read_text()) or {}


def suggested_affixes_for(slot: GearSlot, class_slug: str = "") -> list[str]:
    """Return a flat priority list of affix-name strings for one slot.

    Per-class overlays are appended at the end so that build-specific class
    bonuses appear after the generic slot priorities.
    """
    data = _load()
    slot_entry = (data.get("slots") or {}).get(slot.value, {}) or {}
    out: list[str] = list(slot_entry.get("priority") or [])

    cls_entry = (data.get("classes") or {}).get((class_slug or "").lower(), {}) or {}
    everywhere = list(cls_entry.get("everywhere_bonus") or [])
    if slot.value.startswith("weapon"):
        out.extend(cls_entry.get("weapon_extra") or [])
    if slot.value == "helm":
        out.extend(cls_entry.get("helm_extra") or [])
    out.extend(everywhere)

    # Dedup preserving order.
    seen = set()
    deduped = []
    for x in out:
        if x not in seen:
            seen.add(x)
            deduped.append(x)
    return deduped


def greater_priority_for(slot: GearSlot) -> list[str]:
    data = _load()
    return list(((data.get("slots") or {}).get(slot.value, {}) or {}).get("greater_priority") or [])


def tempering_for(slot: GearSlot) -> list[str]:
    data = _load()
    return list(((data.get("slots") or {}).get(slot.value, {}) or {}).get("tempering") or [])


def masterwork_target_for(slot: GearSlot) -> str:
    data = _load()
    raw = ((data.get("slots") or {}).get(slot.value, {}) or {}).get("masterwork_target")
    return str(raw) if raw else ""
