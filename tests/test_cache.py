"""Tests for the SQLite cache layer."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from d4_build.cache import Cache


@pytest.fixture
def cache(tmp_path: Path) -> Cache:
    return Cache(db_path=tmp_path / "cache.db")


def test_first_call_invokes_fetcher(cache: Cache) -> None:
    calls: list[str] = []

    def fetch() -> str:
        calls.append("fetched")
        return "hello"

    result = cache.get_or_fetch("k1", ttl_seconds=60, fetcher=fetch)
    assert result == "hello"
    assert calls == ["fetched"]


def test_second_call_within_ttl_uses_cache(cache: Cache) -> None:
    calls: list[str] = []

    def fetch() -> str:
        calls.append("x")
        return "value"

    cache.get_or_fetch("k1", ttl_seconds=60, fetcher=fetch)
    cache.get_or_fetch("k1", ttl_seconds=60, fetcher=fetch)
    assert calls == ["x"], "fetcher should only have run once"


def test_call_after_ttl_refetches(cache: Cache) -> None:
    calls: list[str] = []

    def fetch() -> str:
        calls.append("x")
        return f"v{len(calls)}"

    cache.get_or_fetch("k1", ttl_seconds=0, fetcher=fetch)
    time.sleep(0.01)
    result = cache.get_or_fetch("k1", ttl_seconds=0, fetcher=fetch)
    assert calls == ["x", "x"]
    assert result == "v2"


def test_different_keys_isolated(cache: Cache) -> None:
    cache.get_or_fetch("a", ttl_seconds=60, fetcher=lambda: "alpha")
    cache.get_or_fetch("b", ttl_seconds=60, fetcher=lambda: "beta")
    assert cache.get_or_fetch("a", ttl_seconds=60, fetcher=lambda: "WRONG") == "alpha"
    assert cache.get_or_fetch("b", ttl_seconds=60, fetcher=lambda: "WRONG") == "beta"


def test_invalidate_prefix_clears_matching(cache: Cache) -> None:
    cache.get_or_fetch("maxroll:guide:x", ttl_seconds=60, fetcher=lambda: "g")
    cache.get_or_fetch("maxroll:planner:y", ttl_seconds=60, fetcher=lambda: "p")
    cache.get_or_fetch("d4data:skills", ttl_seconds=60, fetcher=lambda: "s")

    n = cache.invalidate_prefix("maxroll:")
    assert n == 2

    calls: list[str] = []

    def f() -> str:
        calls.append("x")
        return "fresh"

    assert cache.get_or_fetch("maxroll:guide:x", ttl_seconds=60, fetcher=f) == "fresh"
    assert cache.get_or_fetch("d4data:skills", ttl_seconds=60, fetcher=f) == "s"
    assert calls == ["x"]


def test_invalidate_all_clears_everything(cache: Cache) -> None:
    cache.get_or_fetch("a", ttl_seconds=60, fetcher=lambda: "1")
    cache.get_or_fetch("b", ttl_seconds=60, fetcher=lambda: "2")
    n = cache.invalidate_all()
    assert n == 2
    calls: list[str] = []

    def f() -> str:
        calls.append("x")
        return "fresh"

    cache.get_or_fetch("a", ttl_seconds=60, fetcher=f)
    cache.get_or_fetch("b", ttl_seconds=60, fetcher=f)
    assert calls == ["x", "x"]


def test_force_refresh_bypasses_cache(cache: Cache) -> None:
    calls: list[str] = []

    def fetch() -> str:
        calls.append("x")
        return f"v{len(calls)}"

    cache.get_or_fetch("k", ttl_seconds=60, fetcher=fetch)
    cache.get_or_fetch("k", ttl_seconds=60, fetcher=fetch, force_refresh=True)
    assert calls == ["x", "x"]
