"""Tests for the d4data display-name lookup."""

from __future__ import annotations

from pathlib import Path

import pytest

from d4_build.sources.d4data import D4DataLookup

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "d4data"


@pytest.fixture
def lookup() -> D4DataLookup:
    return D4DataLookup(d4data_root=FIXTURE_ROOT)


def test_resolves_harlequin_crest(lookup: D4DataLookup) -> None:
    assert lookup.name_for("Helm_Unique_Generic_002") == "Harlequin Crest"


def test_resolves_temerity(lookup: D4DataLookup) -> None:
    assert lookup.name_for("Pants_Unique_Generic_100") == "Temerity"


def test_resolves_class_specific_unique(lookup: D4DataLookup) -> None:
    assert lookup.name_for("2HStaff_Unique_Sorc_002") == "Staff of Endless Rage"


def test_returns_none_for_unknown_id(lookup: D4DataLookup) -> None:
    assert lookup.name_for("Helm_Unique_Generic_NEVERSEEN_999") is None


def test_handles_disabled_root(tmp_path: Path) -> None:
    """When d4data isn't on disk, lookup gracefully returns None."""
    lookup = D4DataLookup(d4data_root=tmp_path / "nonexistent")
    assert lookup.name_for("Helm_Unique_Generic_002") is None
    assert lookup.is_available() is False


def test_is_available_when_root_exists(lookup: D4DataLookup) -> None:
    assert lookup.is_available() is True


def test_caches_repeated_lookups(lookup: D4DataLookup) -> None:
    """The on-disk read should not happen twice for the same id."""
    a = lookup.name_for("Helm_Unique_Generic_002")
    b = lookup.name_for("Helm_Unique_Generic_002")
    assert a == b == "Harlequin Crest"
    # Verify cache by checking the memoization dict for the resolved value.
    assert "Harlequin Crest" in lookup._memo.values()


def test_resolves_glyph_name(lookup: D4DataLookup) -> None:
    assert lookup.glyph_name_for("Rare_010_Dexterity_Main") == "Tactician"


def test_glyph_name_returns_none_for_unknown(lookup: D4DataLookup) -> None:
    assert lookup.glyph_name_for("Rare_NEVERSEEN_999") is None
