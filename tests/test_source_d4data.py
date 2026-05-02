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


def test_humanize_skill_gbid_basic_examples() -> None:
    """The codename humanizer round-trips canonical SkillKit gbid names."""
    from d4_build.sources.d4data import _humanize_skill_gbid

    cases = [
        ("Warlock_Defensive_AbyssDemon1", "Abyss Demon1 (Defensive)"),
        ("Warlock_Core_AbyssDemon", "Abyss Demon (Core)"),
        ("Warlock_Basic_Demon2", "Demon2 (Basic)"),
        ("Warlock_Core_AbyssDemon_Upgrade1", "Abyss Demon — Upgrade 1 (Core)"),
        ("Warlock_Sigil_Abyss", "Abyss (Sigil)"),
        ("Sorcerer_Mastery_FireOrb", "Fire Orb (Mastery)"),
    ]
    for gbid, expected in cases:
        got = _humanize_skill_gbid(gbid)
        assert got == expected, f"{gbid!r}: expected {expected!r}, got {got!r}"


def test_skill_node_label_for_unknown_class_returns_empty(lookup: D4DataLookup) -> None:
    """A class without a SkillKit file returns empty string."""
    assert lookup.skill_node_label_for("notaclass", 761) == ""


def test_skill_node_label_for_handles_string_node_id(lookup: D4DataLookup) -> None:
    """node_id can be passed as int or string."""
    # Both valid string and int IDs should not crash.
    assert isinstance(lookup.skill_node_label_for("warlock", "761"), str)
    assert isinstance(lookup.skill_node_label_for("warlock", 761), str)
    assert lookup.skill_node_label_for("warlock", "not-a-number") == ""


def test_humanize_paragon_node_codename() -> None:
    from d4_build.sources.d4data import _humanize_paragon_node_codename

    cases = [
        ("Generic_Normal_Str", "Strength"),
        ("Generic_Normal_Int", "Intelligence"),
        ("Generic_Normal_Dex", "Dexterity"),
        ("Generic_Normal_Will", "Willpower"),
        ("Generic_Gate", "Gate"),
        ("Generic_Magic_Damage", "Damage (Magic)"),
        ("Generic_Rare_Crit", "Critical (Rare)"),
    ]
    for codename, expected in cases:
        got = _humanize_paragon_node_codename(codename)
        assert got == expected, f"{codename!r}: expected {expected!r}, got {got!r}"


def test_paragon_node_at_returns_codename(lookup: D4DataLookup) -> None:
    """The non-fixture lookup pulls cells from the live d4data clone if present.

    Skip when d4data isn't symlinked into the cache dir.
    """
    from d4_build.sources.d4data import D4DataLookup, default_d4data_root

    real = D4DataLookup()
    if not (real.paragon_board_dir / "Paragon_Warlock_00.pbd.json").exists():
        pytest.skip("d4data Warlock paragon board not present locally")
    # Cell 10 of Paragon_Warlock_00 is 'Generic_Gate' per the file's arEntries[10].
    assert real.paragon_node_at("Paragon_Warlock_00", 10) == "Generic_Gate"
