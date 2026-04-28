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
