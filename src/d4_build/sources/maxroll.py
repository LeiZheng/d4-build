"""Maxroll source adapters: tier list, guide, planner.

Cloudflare blocks plain `httpx` so we use `curl_cffi` with Chrome impersonation.
All fetched content goes through the shared on-disk cache.
"""

from __future__ import annotations

from typing import Callable

from curl_cffi import requests as cf_requests

from ..cache import Cache
from ..config import (
    TTL_GUIDE_SECONDS,
    TTL_INDEX_SECONDS,
    TTL_PLANNER_SECONDS,
    USER_AGENT,
    maxroll_guide_url,
    maxroll_planner_url,
    maxroll_tierlist_url,
)
from ..parsers.guide_html import GuideMeta, parse_guide_html
from ..parsers.planner_remix import PlannerProfileData, parse_planner_html


def _http_get(url: str) -> str:
    r = cf_requests.get(
        url,
        impersonate="chrome120",
        timeout=30,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
    )
    r.raise_for_status()
    return r.text


class MaxrollSource:
    def __init__(self, cache: Cache, fetcher: Callable[[str], str] = _http_get) -> None:
        self.cache = cache
        self._fetcher = fetcher

    def get_guide(self, slug_or_url: str, force_refresh: bool = False) -> GuideMeta:
        url = maxroll_guide_url(slug_or_url)
        html = self.cache.get_or_fetch(
            f"maxroll:guide:{url}",
            ttl_seconds=TTL_GUIDE_SECONDS,
            fetcher=lambda: self._fetcher(url),
            force_refresh=force_refresh,
        )
        meta = parse_guide_html(html)
        return meta

    def get_planner(self, planner_id: str, force_refresh: bool = False) -> PlannerProfileData:
        url = maxroll_planner_url(planner_id)
        html = self.cache.get_or_fetch(
            f"maxroll:planner:{url}",
            ttl_seconds=TTL_PLANNER_SECONDS,
            fetcher=lambda: self._fetcher(url),
            force_refresh=force_refresh,
        )
        return parse_planner_html(html)

    def get_tierlist_html(self, class_slug: str, force_refresh: bool = False) -> str:
        url = maxroll_tierlist_url(class_slug)
        return self.cache.get_or_fetch(
            f"maxroll:tierlist:{url}",
            ttl_seconds=TTL_INDEX_SECONDS,
            fetcher=lambda: self._fetcher(url),
            force_refresh=force_refresh,
        )
