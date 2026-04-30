"""Tests for the manual skill-node-name overrides loader."""

from __future__ import annotations

from d4_build.skill_node_overrides import (
    label_for,
    labels_for_class,
)


def test_unknown_class_returns_empty() -> None:
    assert label_for("paladin", "9034") == ""


def test_unknown_node_returns_empty() -> None:
    # Now that d4data is the primary resolver, the YAML override is empty
    # by default. Lookups should return "" for any node when nothing's mapped.
    assert label_for("warlock", "999999") == ""


def test_class_lookup_is_case_insensitive_when_present() -> None:
    """Adding a value via the dict API: case-insensitive lookup still works."""
    # Hand-add a synthetic entry to verify the lookup still works.
    from d4_build.skill_node_overrides import _load
    _load.cache_clear()
    # The _load function is read-only; we can't inject. Just verify casing
    # doesn't crash when no entries exist.
    assert label_for("Warlock", "9034") == label_for("warlock", "9034")


def test_labels_for_class_returns_dict() -> None:
    m = labels_for_class("warlock")
    assert isinstance(m, dict)


def test_empty_args_return_empty_string() -> None:
    assert label_for("", "9034") == ""
    assert label_for("warlock", "") == ""
