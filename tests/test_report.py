"""End-to-end report rendering: from fixtures to a full Markdown string."""

from __future__ import annotations

import pytest

from d4_build.parsers.guide_html import parse_guide_html
from d4_build.parsers.planner_remix import parse_planner_html
from d4_build.reconcile import reconcile
from d4_build.report.markdown import render_build
from tests.conftest import require_maxroll_fixture


@pytest.fixture
def report_text() -> str:
    guide = parse_guide_html(
        require_maxroll_fixture("blizzard-sorcerer-guide.html").read_text()
    )
    profile = parse_planner_html(
        require_maxroll_fixture("planner-vw1uz0be.html").read_text()
    )
    build = reconcile(
        guide,
        profile,
        guide_url="https://maxroll.gg/d4/build-guides/blizzard-sorcerer-guide",
    )
    return render_build(build)


def test_report_starts_with_archetype_header(report_text: str) -> None:
    assert report_text.startswith("# Blizzard Sorcerer")


def test_report_lists_six_skills(report_text: str) -> None:
    assert "Blizzard" in report_text
    assert "Frost Bolt" in report_text


def test_report_flags_uniques(report_text: str) -> None:
    assert "MUST HAVE" in report_text
    # Per-item detail section labels uniques distinctly.
    assert "_(UNIQUE)" in report_text or "(UNIQUE" in report_text


def test_report_includes_damage_breakdown(report_text: str) -> None:
    assert "Damage breakdown" in report_text
    assert "Dominant bucket" in report_text


def test_report_includes_compare_against_section(report_text: str) -> None:
    assert "Mobalytics" in report_text
    assert "d4builds.gg" in report_text
    assert "Icy Veins" in report_text


def test_report_includes_playtest_checklist(report_text: str) -> None:
    assert "Verify in-game" in report_text
    assert "[ ]" in report_text


def test_report_includes_data_freshness_footer(report_text: str) -> None:
    assert "Data freshness" in report_text
    assert "vw1uz0be" in report_text
    assert "https://maxroll.gg" in report_text
