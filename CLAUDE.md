# d4-build — context for future Claude sessions

This file is loaded automatically when Claude works in this directory. It
captures the project's purpose, the user's working style, and the iterative
decisions that shaped the codebase. Edit when something changes that future
sessions need to know.

---

## What this is

A personal-use Diablo IV character build advisor. Pulls meta builds from
[Maxroll](https://maxroll.gg/d4), enriches them with display names from the
[DiabloTools/d4data](https://github.com/DiabloTools/d4data) datamine, and
emits a duplication-ready Markdown report with the skill bar, click-by-click
skill-point allocation, equipment with rolled affixes + tempering +
masterwork guidance, paragon progression with glyphs, damage-bucket
explainer, and an in-game playtest checklist.

The user is `Lei Zheng` (`lei@flexcompute.com`), a software engineer playing
Diablo IV who wanted reports detailed enough to duplicate a character two
months later without re-reading the source guides. The tool is open-source
on the user's personal GitHub at <https://github.com/LeiZheng/d4-build>.

---

## How the user prompts — summarized arc of the build

Conversation began on 2026-04-26 with a vague "tool to tell players how to
build a Diablo character" and grew through ~25 iterative requests over six
days. The throughline: the user keeps asking for **more concrete output**
and **better verification**, not more abstraction. Notable prompts:

1. **Initial spec** — model skills + equipment + paragon + stats, design
   builds; corrected own assumption that "Crit is the major damage source"
   and asked the tool to explain the math
2. **"high quality data of input is very critical"** — pushed for data
   provenance and quality controls before agreeing to a plan
3. **"each character has their own types for build, you should list the
   options"** — refined the input flow from auto-pick to browse-then-pick
   by archetype
4. **"compare your build with what Maxroll has on the network or with
   popular ones on the internet"** — added cross-source consensus check
   (Mobalytics + d4builds + Icy Veins)
5. **"how do I know the actual name with such 002, 003 id?"** — surfaced the
   d4data integration; user wanted real display names, not internal IDs
6. **"clear point allocation steps of paragon"** — paragon-step expansion
   with per-board snapshots
7. **"detail how to allocate the skill points on skill tree"** — skill-tree
   per-step extraction
8. **"each paragon has the rune embedded"** (rune == glyph in their phrasing) —
   per-board glyph rendering
9. **"try 10 times with different non-fundamental variables, compare damage,
   survive, continuous, provide the best"** — variant scoring engine
   (damage/survive/sustain heuristic, picks best composite)
10. **"detail enough to duplicate the character"** — per-item enrichment with
    implicits/explicits/tempering/aspects/sockets
11. **"let's have build for Warlock for leveling"** — exercised the tool on
    the brand-new class on Lord of Hatred launch day
12. **"push the system to my personal GitHub account"** — public repo created
13. **"sync the data"** + **"build the leveling for Warlock again"** — d4data
    upgraded `2.6.1 → 3.0.1`, Maxroll re-issued the planner; tool worked
    seamlessly across the patch
14. **"clear step about how to click the skill point one by one"** + **"clear
    instruction for affix hunting"** — flat per-level click table + per-slot
    crafting workflow with tempering manuals + masterwork targets
15. **"node XXX should be converted to actual skill name"** — wired
    `D4DataLookup.skill_node_label_for` reading `SkillKit/<Class>.skl.json`
16. **"summary the my prompt and add the CLAUDE.md"** — this file

---

## User preferences observed

These came from explicit corrections or accepted recommendations during the
build. Following them avoids re-litigating settled decisions.

- **Output verification, not just code correctness.** The user pushed back
  twice on a verification plan that only checked "the code runs." Reports
  must include layered verification: fidelity (do we faithfully reproduce
  the source?), cross-source consensus (do other reputable sources agree?),
  and in-game ground truth (does the build actually work when played?).
  This is also captured in `~/.claude/projects/-Users-leizheng-d4/memory/feedback_output_verification.md`.
- **Honesty about limitations.** When data isn't fully resolved (e.g.,
  in-game tooltip strings need a deeper d4data walk we haven't done), the
  report says so explicitly. No fake precision. Heuristic numbers carry
  caveats; raw IDs render with `(unmapped)` markers; sections that depend
  on missing client-side data say "refer to source guide" instead of
  fabricating output.
- **Real names everywhere, internal IDs only as cross-reference.** The user
  reacted to seeing `Helm_Unique_Generic_002` in the report by demanding
  display-name resolution. Subsequent passes added d4data for items,
  glyphs, paragon boards, runes, affix nids, and skill-tree node IDs. Raw
  IDs are kept only as small `<sub>` cross-reference text.
- **Step-by-step, actionable output.** "Clear", "one by one", "detail
  enough to duplicate" came up repeatedly. The reports favor flat tables
  with explicit per-item / per-level / per-slot rows over nested narratives.
- **Iterative refinement is expected.** The user adds requirements rather
  than re-spec'ing. Accept that and don't over-engineer up front; deliver
  working v1 with honest caveats, then enrich.
- **Imperfect English — interpret charitably.** Examples from this thread:
  `"worlark"` / `"woklok"` = Warlock; `"ruin"` = rune (or glyph); `"firebolt"`
  meant Fireball; `"sorc"` build types listed as `"Hydran, Firebolt, Ice,
  Lighting Ball"`. Resolve by context, don't ask for clarification on
  obvious typos.
- **Authorization-aware actions.** The user explicitly authorized the push
  to GitHub after I surfaced public-vs-private + Maxroll-fixture-copyright
  concerns via AskUserQuestion. They appreciated being given the choice.
  Future visibility-changing actions (push, PR, public artifact) should
  similarly surface concerns and confirm scope.

---

## Architecture decisions worth preserving

- **Hybrid recommender + explainer, not a generator.** Maxroll's
  theorycrafters know more than our optimizer would; the tool layers
  *explanation* on top of their builds, not synthesis from scratch.
  Brainstorming explored Generator (Option B) and Hybrid+Generator (Option γ);
  both were correctly rejected as multi-week projects with marginal gain.
- **Cloudflare bypass via `curl_cffi` Chrome impersonation.** Plain httpx
  is rejected at the TLS handshake by Maxroll. `impersonate="chrome120"`
  works. Without this, the entire Maxroll path requires Playwright (200MB+
  headless browser).
- **Maxroll planner data lives in `window.__remixContext`.** Not
  `__NEXT_DATA__` (the original plan agent's assumption was wrong). The
  blob is JSON.parse-able after balanced-brace extraction; the build's
  structured data is at `state.loaderData.d4planner-by-id.profile.data`
  (a JSON-encoded string).
- **d4data is the resolver of last resort, but check d4data first.** Lookup
  chain: d4data StringList → manual override YAML → humanizer → raw ID.
  d4data's `SkillKit/<Class>.skl.json::arNodes` maps planner node IDs
  (`dwID`) to power codenames (`gbidReward.name`).
- **Slot derivation by item-id prefix, not numeric slot index.** Maxroll's
  planner JSON renumbers slot indices between builds (Blizzard 9 slots,
  Ice Shards 10 slots — indices shift). Item IDs like `Helm_Unique_Sorc_002`
  carry the slot type stably.
- **Snapshot tests + skip-when-fixture-missing.** `tests/conftest.py`
  exposes `require_maxroll_fixture(name)` which skips cleanly when the
  fixture is absent (Maxroll content is gitignored as it's copyrighted).
  88 tests pass with fixtures locally, ~47 pass + ~41 skip on a public clone.
- **One-canonical Build model.** Pydantic v2 `Build` is the central type;
  parsers produce it, reconciler merges into it, scorer ranks variants
  into it, explainer reads it, renderer emits Markdown. Every new feature
  added a field rather than a new top-level type.

---

## Working patterns that worked well in this codebase

- **TDD for novel logic** (parsers, scoring, humanizer) — wrote failing
  tests against fixtures first, then minimum implementation. Caught a bunch
  of edge cases (mixed dict/string glyph types in the planner, slot
  renumbering, search_metadata being empty for some builds).
- **Fixture-first scraping.** When reverse-engineering a new source, save
  the raw HTML/JSON to `tests/fixtures/`, write the parser against the
  fixture, then snapshot-test it. Live fetches are for end-to-end smoke
  tests only.
- **Sync ritual after a patch.** The post-Lord-of-Hatred sync (Apr 28→29)
  was: invalidate Maxroll cache, fetch d4data, reset the working tree to
  origin/master, delete the cached affix-nid index, re-render a canonical
  build, verify names resolve. This is a well-defined recipe — see the
  `d4-build refresh` and `d4-build d4data-setup` commands.
- **Two GitHub accounts present (`lei-flex` work + `LeiZheng` personal).**
  `gh auth switch -u LeiZheng` is required before pushes; the active
  account silently flips back to `lei-flex` sometimes. Verify with
  `gh auth status` before pushing.

---

## Open follow-ups (queue, not commitments)

- **Season-drift detection + warning** — pending since Apr 27; would compare
  the guide page's H1 season vs. the tier-list's season and surface a
  banner when they disagree. Maxroll's content drift behavior makes this
  worth shipping but it hasn't blocked anything.
- **In-game tooltip strings for affixes.** The current resolution path
  produces `Cooldown Reduction CDR` (humanized d4data key) instead of the
  in-game tooltip `Up to +X% Cooldown Reduction`. Walking the
  Affix → Power → Attribute → tooltip-string chain in d4data would close
  this gap. ~half-day of work.
- **Per-archetype affix priorities.** The current per-slot table is
  generic; a Bleed Barb wants Bleed Damage everywhere, which the table
  doesn't surface. Would need per-archetype overlays in
  `data/affix_recommendations.yaml`.
- **Tier rank `?`.** Maxroll's S/A/B widget hydrates client-side from an
  API I haven't reverse-engineered. The `list <class>` command has the
  archetype names but the tier column always reads `?`.
- **Stat priorities section is empty.** Same root cause — Maxroll renders
  the priority widget client-side. The report falls back to the curated
  affix-priority list in `data/affix_recommendations.yaml`.
- **Option γ — self-formulated builds with Maxroll/Mobalytics as
  benchmark.** Real generation rather than enrichment. Multi-week effort,
  deferred. The user mentioned this twice but accepted the staged
  hybrid-first approach.
