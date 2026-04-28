"""List available archetypes for a class from Maxroll's tier list pages.

Maxroll's per-class tier list (e.g. /d4/tierlists/sorcerer) is a hub linking to
four sub-tier-lists by role: endgame, leveling, push, speedfarming. Each
sub-page lists the actual archetypes.

The static HTML server-renders the build-guide links and titles but the
tier-rank (S/A/B/C) is hydrated client-side from a separate Maxroll API we
haven't reverse-engineered yet — so v1 returns tier as "?" and lets the
player browse the list. The eventual fix is to call that hydration endpoint.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from ..config import maxroll_tierlist_url
from ..model import BuildSummary

if TYPE_CHECKING:
    from .maxroll import MaxrollSource


_ROLES = ("endgame", "leveling", "push", "speedfarming")


def _slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def _archetype_from_link_text(text: str, class_name: str) -> str:
    """Maxroll labels each link "<Archetype> <Class>" (e.g. "Blizzard Sorc")."""
    # Strip trailing class abbreviation
    text = re.sub(rf"\s+{re.escape(class_name)}.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(Sorc|Barb|Necro|Druid|Rogue|Spiritborn).*$", "", text, flags=re.IGNORECASE)
    return text.strip()


def _parse_tierlist_html(html: str, class_name: str, role: str) -> list[BuildSummary]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[BuildSummary] = []
    for a in soup.find_all("a", href=re.compile(r"/d4/build-guides/")):
        href = a.get("href", "")
        if href in seen:
            continue
        seen.add(href)
        slug = _slug_from_url(href)
        text = a.get_text(strip=True)
        archetype = _archetype_from_link_text(text, class_name)
        if not archetype:
            continue
        out.append(
            BuildSummary(
                id=slug,
                class_id=class_name.lower(),
                archetype=archetype,
                tier="?",
                role=role,
                url=href if href.startswith("http") else f"https://maxroll.gg{href}",
            )
        )
    return out


def list_class_archetypes(
    source: "MaxrollSource",
    class_slug: str,
    *,
    force_refresh: bool = False,
) -> list[BuildSummary]:
    """Aggregate archetypes across the four role-specific sub-tier-lists."""
    summaries: list[BuildSummary] = []
    seen_slugs: set[str] = set()

    for role in _ROLES:
        sub_url = f"{maxroll_tierlist_url(class_slug)}-{role}-tier-list"
        # Maxroll uses two URL patterns: <class>-endgame-tier-list AND
        # <class>-leveling-builds-tier-list / <class>-speedfarming-builds-tier-list.
        # Try both forms.
        for variant in (sub_url, sub_url.replace(f"-{role}-tier-list", f"-{role}-builds-tier-list")):
            try:
                html = source.cache.get_or_fetch(
                    f"maxroll:tierlist:{variant}",
                    ttl_seconds=24 * 3600,
                    fetcher=lambda u=variant: source._fetcher(u),
                    force_refresh=force_refresh,
                )
            except Exception:
                continue
            page_summaries = _parse_tierlist_html(html, class_slug.title(), role)
            if page_summaries:
                for s in page_summaries:
                    if s.id in seen_slugs:
                        continue
                    seen_slugs.add(s.id)
                    summaries.append(s)
                break

    return summaries
