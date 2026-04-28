"""Paths, TTLs, URL templates."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_dir


def cache_dir() -> Path:
    p = Path(user_cache_dir("d4-build"))
    p.mkdir(parents=True, exist_ok=True)
    return p


TTL_GUIDE_SECONDS = 24 * 3600
TTL_PLANNER_SECONDS = 7 * 24 * 3600
TTL_INDEX_SECONDS = 24 * 3600

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

MAXROLL_BASE = "https://maxroll.gg"


def maxroll_guide_url(slug: str) -> str:
    if slug.startswith("http"):
        return slug
    return f"{MAXROLL_BASE}/d4/build-guides/{slug}"


def maxroll_planner_url(planner_id: str) -> str:
    return f"{MAXROLL_BASE}/d4/planner/{planner_id}"


def maxroll_tierlist_url(class_slug: str) -> str:
    return f"{MAXROLL_BASE}/d4/tierlists/{class_slug}"
