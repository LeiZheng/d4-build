"""Resolve a SkillKit gbid (e.g. `Warlock_Core_AbyssDemon_Upgrade2`) to the
real in-game modifier name (e.g. "Cascading Dread") via the manual mapping
in `data/skill_modifier_mapping.yaml`.

Returns "" when the mapping doesn't have an entry — callers fall back to
the codename humanizer.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


_DATA_PATH = Path(__file__).parent / "data" / "skill_modifier_mapping.yaml"


@lru_cache(maxsize=1)
def _load() -> dict[str, dict]:
    if not _DATA_PATH.exists():
        return {}
    raw = yaml.safe_load(_DATA_PATH.read_text()) or {}
    return raw if isinstance(raw, dict) else {}


def parse_gbid(gbid: str) -> tuple[str, str]:
    """Split `Warlock_Core_AbyssDemon_Upgrade2` -> (`Warlock_Core_AbyssDemon`, `Upgrade2`).

    Returns (gbid, "") when there's no Upgrade suffix.
    """
    if not gbid:
        return "", ""
    parts = gbid.split("_")
    # The last token is the upgrade marker if it starts with 'Upgrade' (e.g.
    # 'Upgrade1', 'UpgradeA').
    if parts and parts[-1].startswith("Upgrade"):
        return "_".join(parts[:-1]), parts[-1]
    return gbid, ""


def resolve_modifier_name(gbid: str) -> tuple[str, str]:
    """Return (skill_display, modifier_name) for a SkillKit gbid.

    `skill_display` is the user-facing skill name (e.g. "Dread Claws").
    `modifier_name` is the upgrade variant (e.g. "Cascading Dread", or
    "Enhanced Dread Claws" for Upgrade1).

    Either may be "" when the mapping doesn't cover this gbid.
    """
    base, suffix = parse_gbid(gbid)
    if not base:
        return "", ""
    entry = _load().get(base)
    if not entry:
        return "", ""
    skill_display = str(entry.get("display_name", ""))
    if not suffix:
        return skill_display, ""
    upgrades = entry.get("upgrades") or {}
    modifier = str(upgrades.get(suffix, ""))
    return skill_display, modifier
