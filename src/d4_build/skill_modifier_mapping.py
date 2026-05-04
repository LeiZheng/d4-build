"""Resolve a SkillKit gbid (e.g. `Warlock_Core_AbyssDemon_Upgrade2`) to the
real in-game modifier name (e.g. "Cascading Dread") via the manual mapping
in `data/skill_modifier_mapping.yaml`.

The YAML carries (display_name, power_file) per skill codename. Per-Upgrade
modifier names are auto-extracted at runtime from the Power file's `arMods`
list, sorted by `dwModId` ascending — index N of the sorted list maps to
Upgrade2/3/4/A/B/C in order.

Optional `upgrades:` overrides in the YAML take precedence (use them when
the auto-extracted ordering doesn't match Maxroll's UI for a particular
skill).

Returns "" when the mapping doesn't have an entry — callers fall back to
the codename humanizer.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


_DATA_PATH = Path(__file__).parent / "data" / "skill_modifier_mapping.yaml"

# Canonical order: how the Upgrade suffix maps to indices in the sorted-by-id
# Mod list. Empirically Upgrade2..Upgrade4 then UpgradeA..UpgradeC.
_AUTO_UPGRADE_ORDER = ("Upgrade2", "Upgrade3", "Upgrade4", "UpgradeA", "UpgradeB", "UpgradeC")


@lru_cache(maxsize=1)
def _load() -> dict[str, dict]:
    if not _DATA_PATH.exists():
        return {}
    raw = yaml.safe_load(_DATA_PATH.read_text()) or {}
    return raw if isinstance(raw, dict) else {}


_CLUSTER_KEYWORDS = (
    "Basic", "Core", "Defensive", "Sigil", "Mastery",
    "Archfiend", "Ultimate", "Capstone", "Special",
)


def _cluster_from_codename(codename: str) -> str:
    """Pull cluster name from `Warlock_Core_AbyssDemon` -> `Core`."""
    parts = codename.split("_")
    for p in parts[1:]:
        if p in _CLUSTER_KEYWORDS:
            return p
    return ""


@lru_cache(maxsize=1)
def display_name_to_cluster() -> dict[str, str]:
    """Reverse-map display_name -> cluster using YAML codename keys."""
    out: dict[str, str] = {}
    for codename, entry in _load().items():
        if not isinstance(entry, dict):
            continue
        cluster = _cluster_from_codename(codename)
        name = entry.get("display_name")
        if cluster and name:
            # First entry wins; multiple codenames can share a display_name
            # (e.g., AbyssDemon1 vs AbyssDemon2 both = "Sigil of Subversion (Defensive)").
            # Prefer the cluster if not already mapped.
            out.setdefault(name, cluster)
    return out


def parse_gbid(gbid: str) -> tuple[str, str]:
    """Split `Warlock_Core_AbyssDemon_Upgrade2` -> (`Warlock_Core_AbyssDemon`, `Upgrade2`)."""
    if not gbid:
        return "", ""
    parts = gbid.split("_")
    if parts and parts[-1].startswith("Upgrade"):
        return "_".join(parts[:-1]), parts[-1]
    return gbid, ""


def resolve_modifier_name(gbid: str, lookup=None) -> tuple[str, str]:
    """Return (skill_display, modifier_name) for a SkillKit gbid.

    Args:
        gbid: SkillKit codename like `Warlock_Core_AbyssDemon_Upgrade2`.
        lookup: optional D4DataLookup instance — if provided, modifier names
            are auto-extracted from Power files unless the YAML overrides.
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

    # 1. Manual override in YAML wins.
    upgrades = entry.get("upgrades") or {}
    if suffix in upgrades:
        return skill_display, str(upgrades[suffix])

    # 2. Upgrade1 is always the "Enhanced" flat buff variant. If the YAML
    # carries an enhanced_description, append it for clarity.
    if suffix == "Upgrade1" and skill_display:
        enh_desc = entry.get("enhanced_description") or ""
        if enh_desc:
            return skill_display, f"Enhanced {skill_display} — {enh_desc}"
        return skill_display, f"Enhanced {skill_display}"

    # 3. Auto-extract from Power file via lookup.
    power_file = entry.get("power_file")
    if not power_file or not lookup:
        return skill_display, ""

    mod_names = lookup.power_mod_names_in_id_order(power_file)
    if not mod_names:
        return skill_display, ""

    # The Upgrade suffixes after Upgrade1 (Enhanced) map onto sorted Mod ids
    # in the canonical order Upgrade2, Upgrade3, Upgrade4, UpgradeA, B, C.
    if suffix in _AUTO_UPGRADE_ORDER:
        idx = _AUTO_UPGRADE_ORDER.index(suffix)
        if idx < len(mod_names):
            return skill_display, mod_names[idx]

    return skill_display, ""
