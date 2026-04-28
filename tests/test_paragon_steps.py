"""Paragon step extraction from planner data."""

from __future__ import annotations

from pathlib import Path

import pytest

from d4_build.parsers.guide_html import parse_guide_html
from d4_build.parsers.planner_remix import parse_planner_html
from d4_build.reconcile import reconcile
from d4_build.sources.d4data import D4DataLookup
from tests.conftest import D4DATA_FIXTURE_DIR, require_maxroll_fixture


@pytest.fixture
def real_build_with_d4data():
    guide_html = require_maxroll_fixture("blizzard-sorcerer-guide.html").read_text()
    planner_html = require_maxroll_fixture("planner-vw1uz0be.html").read_text()
    meta = parse_guide_html(guide_html)
    profile = parse_planner_html(planner_html)
    lookup = D4DataLookup(d4data_root=D4DATA_FIXTURE_DIR)
    return reconcile(
        meta,
        profile,
        guide_url="https://maxroll.gg/d4/build-guides/blizzard-sorcerer-guide",
        d4data=lookup,
    )


def test_build_has_paragon_steps(real_build_with_d4data) -> None:
    assert len(real_build_with_d4data.paragon_steps) > 0


def test_each_step_has_a_name_and_order(real_build_with_d4data) -> None:
    for step in real_build_with_d4data.paragon_steps:
        assert step.name
        assert step.order > 0


def test_steps_have_per_board_node_counts(real_build_with_d4data) -> None:
    """At least one board snapshot in at least one step has a node_count > 0."""
    nonzero = [
        bs for step in real_build_with_d4data.paragon_steps
        for bs in step.boards
        if bs.node_count > 0
    ]
    assert len(nonzero) > 0


def test_step_order_is_sequential(real_build_with_d4data) -> None:
    orders = [s.order for s in real_build_with_d4data.paragon_steps]
    assert orders == sorted(orders)
    assert orders[0] == 1


def test_d4data_resolves_uniques_in_build(real_build_with_d4data) -> None:
    """Items whose Maxroll id matches a fixture StringList should resolve."""
    item_names = {it.name for it in real_build_with_d4data.gear.values()}
    # We have Helm_Unique_Generic_002 -> Harlequin Crest in the d4data fixture.
    # The Blizzard build may or may not use that exact id — just verify *some*
    # name in the build matches a fixture-known unique if applicable.
    fixture_known = {
        "Harlequin Crest",
        "Shroud of False Death",
        "Staff of Endless Rage",
        "Gloves of the Illuminator",
        "Temerity",
        "Ring of Starless Skies",
    }
    overlap = item_names & fixture_known
    assert overlap, f"expected some d4data resolution; got {item_names}"
