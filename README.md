# d4-build

Diablo IV character build advisor. Recommends a meta build (sourced from
[Maxroll](https://maxroll.gg/d4)), enriches it with [d4data](https://github.com/DiabloTools/d4data)
display names, and emits a duplication-ready Markdown report — including
skill-bar order, point-allocation milestones, equipment with rolled affixes,
paragon-board progression with glyphs, and a damage-bucket explainer that
corrects the common "Crit is king" misconception.

## Why this exists

Most D4 build guides are great at *what* to do but thin on *why*. This tool
turns Maxroll's curated builds into reports that name the dominant damage
bucket for each specific build, list affix priorities per slot, and walk the
paragon allocation step by step. You can hand the resulting Markdown to
yourself two months from now and reproduce the character without re-reading
the source guide.

It does **not** synthesize builds from scratch — that requires solving the
Diablo IV damage formula, which is undocumented and reverse-engineered. The
honest answer is "Maxroll's theorycrafters know more than my optimizer
would," so this tool layers explanation on top of their work rather than
competing with it.

## Install

Requires Python 3.12+. Uses [`uv`](https://github.com/astral-sh/uv) to manage
the virtualenv.

```bash
git clone https://github.com/<you>/d4-build.git
cd d4-build
uv venv --python 3.12
uv pip install -e ".[dev]"
```

Optional but recommended for full name resolution — sparse-clone d4data
(~tens of MB instead of 4.6 GB):

```bash
.venv/bin/d4-build d4data-setup
```

## Use

```bash
# List current Maxroll archetypes for a class
.venv/bin/d4-build list sorcerer

# Render a full report for one build
.venv/bin/d4-build show fireball-sorcerer-guide --out build-report.md

# Force re-fetch all cached pages
.venv/bin/d4-build refresh

# After a season patch, refresh the d4data clone too
rm -rf ~/Library/Caches/d4-build/d4data
.venv/bin/d4-build d4data-setup
```

## What's in the report

1. **Variant comparison** — every Maxroll planner ships 3-5 named variants
   (Mythic / Ancestral / Starter / Leveling / Skill Progression). The tool
   scores each on Damage / Survive / Sustain (heuristic 0-100 indices) and
   picks the best composite for the body of the report.
2. **Skill bar** — six slots in order, plus Sorcerer Enchantments / class
   equivalents.
3. **Skill-tree milestones** — cumulative point counts at named breakpoints
   (e.g. "lvl 4 Core" → "lvl 9 Eviscerate" → ... → "lvl 70 All Points") with
   specific node IDs activated at each step.
4. **Equipment** — uniques flagged as `MUST HAVE`, plus per-item detail with
   implicits, explicits (with `[GA]` greater-affix markers), tempering,
   masterwork upgrades, sockets, and a curated affix-priority list per slot.
5. **Paragon** — board sequence with rotation (N/E/S/W), per-step point
   counts per board, and the glyph for each board with rank.
6. **Damage-bucket explainer** — names the dominant bucket for *this* build
   and explains why specific affixes/nodes matter. Corrects "Crit is king"
   when other multiplicative buckets actually dominate.
7. **In-game playtest checklist** — three items the player runs in 15 min to
   confirm the build is working: training-dummy damage range, expected pit
   tier, resource feel.
8. **Compare-against block** — auto-generated URLs to the equivalent build
   on Mobalytics, d4builds.gg, and Icy Veins for manual cross-checking.
9. **Data freshness footer** — fetch timestamps, planner ID, source URLs.

## Architecture

```
src/d4_build/
├── cli.py                     # Typer entry: list | show | refresh | d4data-setup
├── cache.py                   # SQLite cache with TTL + prefix invalidation
├── humanize.py                # d4data-key → readable English (S04_LifePerHit → Life Per Hit)
├── reconcile.py               # merges guide + planner + d4data → Build
├── scoring.py                 # variant Damage/Survive/Sustain scorer
├── skill_node_overrides.py    # manual node-id → name table (sunset when d4data updates)
├── affix_recommendations.py   # per-slot + per-class affix priority
├── parsers/
│   ├── guide_html.py          # H1/role/season/data-d4-id span extractor
│   └── planner_remix.py       # Maxroll's __remixContext blob parser
├── sources/
│   ├── d4data.py              # display-name resolver (item, glyph, paragon board, rune)
│   ├── maxroll.py             # cached HTTP source for guide + planner
│   └── maxroll_index.py       # tier-list page → [BuildSummary]
├── explain/buckets.py         # damage-bucket explainer with archetype heuristics
├── report/
│   ├── markdown.py            # Jinja-driven render
│   └── templates/build-report.md.j2
├── data/
│   ├── affix_recommendations.yaml   # curated per-slot affix priorities
│   └── skill_node_overrides.yaml    # manual class node-id → name (stopgap)
└── model/                     # Pydantic types: Build, Item, ItemAffix, ParagonStep, ...
```

## Data sources

| Source | Used for | Reachability |
|--------|----------|--------------|
| [Maxroll](https://maxroll.gg/d4) build guides | meta archetype + skill bar + section prose | Cloudflare-protected; we use `curl_cffi` Chrome impersonation |
| Maxroll planner | full structured build (items, paragon, skill tree) via the page's `window.__remixContext` blob | same |
| Maxroll tier lists | listing classes' archetypes per role | same |
| [DiabloTools/d4data](https://github.com/DiabloTools/d4data) | item names, glyph names, paragon board names, rune names, affix-key resolution | direct git clone, no scraping |

The tool caches everything to `~/Library/Caches/d4-build/cache.db` (SQLite)
with per-source TTLs (24h for guide HTML, 7d for planner JSON). The d4data
clone lives at `~/Library/Caches/d4-build/d4data`.

## Honest caveats

- **Damage-bucket numbers are heuristic, not in-game truth.** Real per-affix
  marginal analysis needs d4data affix-pool definitions wired through. The
  *dominant* bucket per archetype matches published meta consensus; the
  per-bucket percentages are stylized.
- **Tier rank shows `?`** because Maxroll's tier-rank widget is hydrated
  client-side from an API I haven't reverse-engineered.
- **Stat-priority section is empty** for the same reason — Maxroll renders
  the priority table client-side. The report falls back to the curated
  affix-priority list in `data/affix_recommendations.yaml`.
- **Skill-tree node names** are resolved by:
  1. d4data StringList (works for already-released classes)
  2. `data/skill_node_overrides.yaml` (manual, currently has Warlock entries
     for Lord of Hatred since d4data hadn't shipped Warlock data yet)
  3. Raw node ID as fallback
- **Maxroll's content is copyrighted.** This repo doesn't redistribute it —
  fixtures under `tests/fixtures/maxroll/` are gitignored. Tests that depend
  on those fixtures auto-skip when they're missing.

## Tests

```bash
.venv/bin/pytest
```

The suite has ~90 tests covering the data model, cache, parsers, source
adapters, scoring, humanizer, name resolution, and end-to-end report
rendering. With Maxroll fixtures present locally, all pass; without them,
~50 tests skip cleanly and the rest still pass.

## License

MIT — see [LICENSE](./LICENSE).

This tool is a personal utility for Diablo IV players. It is not affiliated
with Blizzard, Maxroll, Mobalytics, d4builds.gg, Icy Veins, or
DiabloTools/d4data.
