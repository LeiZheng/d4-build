"""Tests for the manual skill-node-name overrides loader."""

from __future__ import annotations

from d4_build.skill_node_overrides import (
    label_for,
    labels_for_class,
)


def test_warlock_basic_skill_resolves() -> None:
    assert label_for("warlock", "9034") == "Hellion Sting (Basic)"


def test_warlock_universal_passive_resolves() -> None:
    assert "universal" in label_for("warlock", "9169").lower()


def test_unknown_class_returns_empty() -> None:
    assert label_for("paladin", "9034") == ""


def test_unknown_node_returns_empty() -> None:
    assert label_for("warlock", "999999") == ""


def test_class_lookup_is_case_insensitive() -> None:
    assert label_for("Warlock", "9034") == label_for("warlock", "9034")


def test_labels_for_class_returns_dict() -> None:
    m = labels_for_class("warlock")
    assert isinstance(m, dict)
    assert "9034" in m


def test_empty_args_return_empty_string() -> None:
    assert label_for("", "9034") == ""
    assert label_for("warlock", "") == ""
