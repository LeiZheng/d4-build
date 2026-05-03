"""Parse a Maxroll D4 build guide HTML page.

A guide page is server-rendered HTML. Selectors of interest:
- <h1>:                                page title carrying archetype/class/role/season
- elements with data-d4-profile="...": link to the planner profile (build data lives there)
- <span data-d4-id="<num>">:           every game-entity reference in the article body
- <h2>/<h3>:                           section headings used to slice prose

This module is the only place that knows the page structure. If Maxroll
changes its DOM, the snapshot test in tests/test_parser_guide.py breaks loudly.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict


class EntityRef(BaseModel):
    """A `<span data-d4-id="N">Name</span>` reference inside the article body."""

    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


class GuideMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    archetype: str
    class_name: str
    role: str
    season: str
    planner_id: str
    referenced_entities: list[EntityRef] = []
    sections: dict[str, str] = {}


# Maxroll H1 format: "<Archetype> <Class> <Role> Build Guide for Diablo IV <Season> ..."
# Examples:
#   Blizzard Sorcerer Endgame Build Guide for Diablo IV Season 12 - Slaughter
#   Hydra Sorcerer Leveling Build Guide for Diablo IV Season 11 - Sins of the Horadrim
_KNOWN_CLASSES = (
    "Barbarian",
    "Druid",
    "Necromancer",
    "Rogue",
    "Sorcerer",
    "Spiritborn",
    "Warlock",
)
_KNOWN_ROLES = ("Endgame", "Leveling", "Speed Farm", "Boss", "Starter")


def _parse_h1(h1_text: str) -> tuple[str, str, str, str]:
    """Return (archetype, class_name, role, season)."""
    txt = h1_text.strip()

    cls = ""
    archetype = ""
    role = ""
    for k in _KNOWN_CLASSES:
        m = re.search(rf"\b{k}\b", txt)
        if m:
            cls = k
            archetype = txt[: m.start()].strip()
            after = txt[m.end():].strip()
            for r in _KNOWN_ROLES:
                rm = re.search(rf"\b{r}\b", after, flags=re.IGNORECASE)
                if rm:
                    role = r
                    break
            break

    season_match = re.search(r"Season\s+\d+(?:\s*-\s*[^|]+)?", txt)
    season = season_match.group(0).strip() if season_match else ""

    return archetype, cls, role, season


def _extract_section_prose(soup: BeautifulSoup, heading: str) -> str:
    """Return concatenated text under the matching H2/H3 until the next same-or-higher heading."""
    target = soup.find(["h2", "h3"], string=re.compile(rf"^{re.escape(heading)}$", re.I))
    if not target:
        return ""
    parts: list[str] = []
    target_level = int(target.name[1])
    for sib in target.find_next_siblings():
        if sib.name and sib.name.startswith("h"):
            level = int(sib.name[1])
            if level <= target_level:
                break
        if sib.name in ("p", "ul", "ol", "div"):
            txt = sib.get_text(" ", strip=True)
            if txt:
                parts.append(txt)
    return "\n\n".join(parts)


def parse_guide_html(html: str) -> GuideMeta:
    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    archetype, cls, role, season = _parse_h1(title)

    planner_id = ""
    prof = soup.find(attrs={"data-d4-profile": True})
    if prof:
        planner_id = prof.get("data-d4-profile", "")
    if not planner_id:
        # Endgame guides reference the planner via URL only. Skip the
        # `builds` index page; pick the first real planner id.
        for m in re.finditer(r"/d4/planner/([a-z0-9]{6,12})", html):
            cand = m.group(1)
            if cand != "builds":
                planner_id = cand
                break

    refs: list[EntityRef] = []
    seen: set[int] = set()
    for span in soup.find_all(attrs={"data-d4-id": True}):
        try:
            did = int(span["data-d4-id"])
        except (TypeError, ValueError):
            continue
        if did in seen:
            continue
        name = span.get_text(strip=True)
        if not name:
            continue
        seen.add(did)
        refs.append(EntityRef(id=did, name=name))

    sections = {
        h: _extract_section_prose(soup, h)
        for h in (
            "Skill Rotation",
            "Skills & Gameplay",
            "Paragon & Glyphs",
            "Items, Mercs & Runes",
            "Season Theme",
            "Class Mechanic - Soul Shards",
            "How To Level",
            "Campaign Leveling",
            "Seasonal / Alt Leveling",
            "Tips and Tricks",
            "Speedrun Route",
            "Endgame Transition",
            "Final Journey to Level 70",
            "Skill Tree Progression",
        )
    }

    return GuideMeta(
        title=title,
        archetype=archetype,
        class_name=cls,
        role=role,
        season=season,
        planner_id=planner_id,
        referenced_entities=refs,
        sections=sections,
    )
