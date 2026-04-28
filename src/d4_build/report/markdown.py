"""Render a Build to Markdown."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..explain.buckets import explain_damage
from ..model import Build, DamageBreakdown


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(default=False),
    trim_blocks=False,
    lstrip_blocks=False,
)


def render_build(build: Build, breakdown: DamageBreakdown | None = None) -> str:
    if breakdown is None:
        breakdown = explain_damage(build)
    template = _env.get_template("build-report.md.j2")
    return template.render(build=build, breakdown=breakdown)
