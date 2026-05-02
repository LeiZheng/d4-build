"""d4-build command-line entry."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .cache import Cache
from .config import cache_dir
from .reconcile import reconcile
from .report.markdown import render_build
from .sources.d4data import D4DataLookup, default_d4data_root
from .sources.maxroll import MaxrollSource
from .sources.maxroll_index import list_class_archetypes

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Diablo IV character build advisor — recommends a meta build, explains the math.",
)
console = Console()


def _make_source(force_refresh: bool = False) -> MaxrollSource:
    cache = Cache(db_path=cache_dir() / "cache.db")
    if force_refresh:
        cache.invalidate_all()
    return MaxrollSource(cache=cache)


@app.command("list")
def list_cmd(
    class_name: str = typer.Argument(
        ..., help="Class slug: barbarian | druid | necromancer | rogue | sorcerer | spiritborn"
    ),
    refresh: bool = typer.Option(False, "--refresh", help="Force re-fetch."),
) -> None:
    """List current Maxroll build archetypes for a class."""
    source = _make_source(force_refresh=refresh)
    try:
        summaries = list_class_archetypes(source, class_name.lower(), force_refresh=refresh)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]could not fetch tier list: {exc}[/red]")
        raise typer.Exit(code=2)

    if not summaries:
        console.print(f"[yellow]no archetypes found for {class_name}[/yellow]")
        raise typer.Exit(code=1)

    table = Table(title=f"{class_name.title()} builds (Maxroll)")
    table.add_column("ID")
    table.add_column("Archetype")
    table.add_column("Tier")
    table.add_column("Role")
    for s in summaries:
        table.add_row(s.id, s.archetype, s.tier, s.role)
    console.print(table)


@app.command("show")
def show_cmd(
    slug: str = typer.Argument(
        ...,
        help="Maxroll guide slug, e.g. 'blizzard-sorcerer-guide', "
        "or full URL to the guide page.",
    ),
    out: Path = typer.Option(
        Path("build-report.md"), "--out", "-o", help="Output path."
    ),
    refresh: bool = typer.Option(False, "--refresh", help="Force re-fetch."),
    points: int = typer.Option(
        0,
        "--points",
        "-p",
        help="If >0, truncate the click-by-click skill-point table after this "
        "many points (useful for showing 'allocate at level X'). 0 = full sequence.",
    ),
) -> None:
    """Fetch a Maxroll guide + planner, render the build report."""
    source = _make_source(force_refresh=refresh)

    try:
        meta = source.get_guide(slug, force_refresh=refresh)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]failed to fetch guide '{slug}': {exc}[/red]")
        raise typer.Exit(code=2)

    if not meta.planner_id:
        console.print(
            "[red]guide has no embedded planner profile id; cannot extract build[/red]"
        )
        raise typer.Exit(code=2)

    try:
        profile = source.get_planner(meta.planner_id, force_refresh=refresh)
    except Exception as exc:  # noqa: BLE001
        console.print(
            f"[red]failed to fetch planner '{meta.planner_id}': {exc}[/red]"
        )
        raise typer.Exit(code=2)

    guide_url = (
        slug
        if slug.startswith("http")
        else f"https://maxroll.gg/d4/build-guides/{slug}"
    )
    d4data = D4DataLookup()
    build = reconcile(meta, profile, guide_url=guide_url, d4data=d4data)
    if points and points > 0:
        build = build.model_copy(update={
            "skill_point_clicks": build.skill_point_clicks[:points],
        })
    md = render_build(build)
    out.write_text(md)
    d4data_note = (
        ""
        if d4data.is_available()
        else f" [yellow](d4data not installed at {default_d4data_root()} — unique names won't resolve; run `d4-build d4data-setup`)[/yellow]"
    )
    console.print(
        f"[green]Wrote {out}[/green] "
        f"({build.archetype} {build.class_.name}, "
        f"{len(build.skills_in_order)} skills, "
        f"{len(build.gear)} gear slots){d4data_note}"
    )


@app.command("optimize")
def optimize_cmd(
    slug: str = typer.Argument(..., help="Maxroll guide slug or full URL."),
    points: int = typer.Option(40, "--points", "-p", help="Points to allocate."),
    gear_tier: str = typer.Option(
        "ancestral",
        "--tier",
        help="Gear tier baseline: sacred / ancestral / legendary / mythic.",
    ),
    refresh: bool = typer.Option(False, "--refresh", help="Force re-fetch."),
    show_marginals: bool = typer.Option(
        False, "--marginals", help="Print per-point marginal Δ table."
    ),
    run_search: bool = typer.Option(
        False, "--search", help="Run greedy hill-climb search over the full SkillKit."
    ),
) -> None:
    """Run the heuristic skill-allocation optimizer for a build."""
    from .optimize.skill_allocation import optimize as run_optimize
    from .optimize.marginal import compute_marginals
    from .optimize.search import greedy_search

    source = _make_source(force_refresh=refresh)
    meta = source.get_guide(slug, force_refresh=refresh)
    if not meta.planner_id:
        console.print("[red]guide has no embedded planner[/red]")
        raise typer.Exit(code=2)
    profile = source.get_planner(meta.planner_id, force_refresh=refresh)
    guide_url = (
        slug if slug.startswith("http")
        else f"https://maxroll.gg/d4/build-guides/{slug}"
    )
    d4data = D4DataLookup()
    build = reconcile(meta, profile, guide_url=guide_url, d4data=d4data)

    result = run_optimize(build, gear_tier=gear_tier, total_points=points)

    console.print(
        f"\n[bold]Optimizer for {build.archetype} {build.class_.name}[/bold] "
        f"({points} points, {gear_tier} gear)\n"
    )
    table = Table(title="Candidate sequences (sorted by composite score)")
    table.add_column("Candidate")
    table.add_column("Damage", justify="right")
    table.add_column("Survive", justify="right")
    table.add_column("Sustain", justify="right")
    table.add_column("Composite", justify="right")
    table.add_column("Δ vs baseline", justify="right")
    for c in sorted(result.candidates, key=lambda x: -x.stats.composite_score):
        marker = " ◀" if c.name == result.best_name else ""
        table.add_row(
            c.name + marker,
            f"{c.stats.damage_score:.1f}",
            f"{c.stats.survive_score:.1f}",
            f"{c.stats.sustain_score:.1f}",
            f"{c.stats.composite_score:.1f}",
            f"{c.delta_vs_baseline:+.2f}",
        )
    console.print(table)
    console.print(
        f"\n[green]Best: {result.best_name}[/green] "
        f"(+{result.best_delta:.2f} composite vs Maxroll baseline)"
    )
    if result.best_name == result.baseline_name:
        console.print(
            "[yellow]Note: Maxroll's baseline already wins. The other candidates "
            "are intermediate-state perturbations that score lower under this "
            "heuristic.[/yellow]"
        )
    console.print(f"\n[dim]{result.notes}[/dim]")

    if show_marginals:
        from .optimize.skill_allocation import _scale_build_to_tier
        scaled = _scale_build_to_tier(build, gear_tier)
        truncated = scaled.model_copy(update={
            "skill_point_clicks": scaled.skill_point_clicks[:points],
        })
        marginals = compute_marginals(truncated)
        console.print(f"\n[bold]Per-point marginal table (Maxroll baseline, {gear_tier} gear, {points} points)[/bold]")
        mtable = Table(show_header=True)
        mtable.add_column("Lvl", justify="right")
        mtable.add_column("#", justify="right")
        mtable.add_column("Click on")
        mtable.add_column("ΔDmg", justify="right")
        mtable.add_column("ΔSurv", justify="right")
        mtable.add_column("ΔSust", justify="right")
        mtable.add_column("ΔComp", justify="right")
        mtable.add_column("Cum.Comp", justify="right")
        for m in marginals:
            label = m.node_label
            if m.new_rank > 1:
                label += f" → r{m.new_rank}"
            mtable.add_row(
                str(m.level),
                str(m.point_number),
                label[:40],
                f"{m.delta_damage:+.2f}",
                f"{m.delta_survive:+.2f}",
                f"{m.delta_sustain:+.2f}",
                f"{m.delta_composite:+.2f}",
                f"{m.cumulative_composite:.1f}",
            )
        console.print(mtable)

    if run_search:
        from .optimize.skill_allocation import _scale_build_to_tier
        scaled = _scale_build_to_tier(build, gear_tier)
        console.print(
            f"\n[bold]Greedy hill-climb over the full {build.class_.name} SkillKit[/bold] "
            f"({points} points, {gear_tier} gear)"
        )
        sr = greedy_search(
            scaled,
            total_points=points,
            class_slug=build.class_.id,
            d4data=d4data,
        )
        if not sr.plan:
            console.print(f"[red]search failed: {sr.notes}[/red]")
        else:
            stable = Table(show_header=True, title="Greedy plan")
            stable.add_column("Lvl", justify="right")
            stable.add_column("#", justify="right")
            stable.add_column("Click on")
            stable.add_column("Rank", justify="right")
            for c in sr.plan:
                stable.add_row(
                    str(c.level),
                    str(c.point_number),
                    c.node_label[:50],
                    f"{c.new_rank}",
                )
            console.print(stable)
            console.print(
                f"\n[green]Greedy final composite: {sr.final_stats.composite_score:.2f}[/green] "
                f"(damage={sr.final_stats.damage_score:.1f}, "
                f"survive={sr.final_stats.survive_score:.1f}, "
                f"sustain={sr.final_stats.sustain_score:.1f})"
            )
            baseline_composite = result.baseline_stats.composite_score
            delta = sr.final_stats.composite_score - baseline_composite
            console.print(
                f"  vs Maxroll baseline: composite {baseline_composite:.2f} "
                f"({'+' if delta >= 0 else ''}{delta:.2f})"
            )
            console.print(f"\n[dim]{sr.notes}[/dim]")


@app.command("refresh")
def refresh_cmd() -> None:
    """Clear all cached pages so the next run re-fetches."""
    cache = Cache(db_path=cache_dir() / "cache.db")
    n = cache.invalidate_all()
    console.print(f"[green]cleared {n} cache entries[/green]")


@app.command("d4data-setup")
def d4data_setup_cmd(
    full: bool = typer.Option(
        False,
        "--full",
        help="Clone the full repo (~4.6 GB). Default is sparse: just the "
        "English StringList directory (~tens of MB).",
    ),
) -> None:
    """Sparse-clone DiabloTools/d4data so unique items resolve to display names."""
    import shutil
    import subprocess

    target = default_d4data_root()
    if target.exists():
        console.print(
            f"[yellow]d4data already at {target}. "
            f"Remove first with: rm -rf {target}[/yellow]"
        )
        raise typer.Exit(code=1)

    target.parent.mkdir(parents=True, exist_ok=True)
    repo = "https://github.com/DiabloTools/d4data.git"

    if full:
        console.print(
            f"[blue]Full clone (this is ~4.6 GB and will take a while)…[/blue]"
        )
        subprocess.run(
            ["git", "clone", "--depth", "1", repo, str(target)], check=True
        )
    else:
        console.print(
            f"[blue]Sparse clone of StringList only (~tens of MB)…[/blue]"
        )
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--no-checkout",
                "--sparse",
                repo,
                str(target),
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "sparse-checkout", "init", "--cone"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(target),
                "sparse-checkout",
                "set",
                "json/enUS_Text/meta/StringList",
            ],
            check=True,
        )
        subprocess.run(["git", "-C", str(target), "checkout"], check=True)

    lookup = D4DataLookup()
    if lookup.is_available():
        size = sum(
            f.stat().st_size for f in lookup.stringlist_dir.glob("*.json")
        )
        console.print(
            f"[green]d4data ready at {target}[/green]\n"
            f"  {len(list(lookup.stringlist_dir.glob('*.json')))} StringList files, "
            f"{size / (1024 * 1024):.1f} MB"
        )
    else:
        console.print("[red]clone completed but StringList not found — try --full[/red]")
        raise typer.Exit(code=2)


def main() -> None:
    app()


if __name__ == "__main__":
    sys.exit(main())
