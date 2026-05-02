"""Merge guide + planner into a single typed Build.

For v1 we use Maxroll's `search_metadata` for human-readable item/skill names
and pull all structural fields (skill bar, paragon order) from the planner's
inner profile.data. Damage-bucket affixes will be filled in later when d4data
is integrated.

The "endgame" variant is preferred when available (Mythic > Ancestral > others).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .affix_recommendations import (
    masterwork_target_for,
    suggested_affixes_for,
    tempering_for,
)
from .config import maxroll_guide_url, maxroll_planner_url
from .humanize import humanize_key
from .model import (
    Build,
    GameClass,
    GearSlot,
    Item,
    ItemAffix,
    ParagonBoard,
    ParagonBoardSnapshot,
    ParagonStep,
    Skill,
    SkillPointClick,
    SkillTreeStep,
    StatPriority,
    VariantScore,
)
from .scoring import best_variant_name, score_all_variants
from .skill_node_overrides import label_for as _node_override_for
from .parsers.guide_html import GuideMeta
from .parsers.planner_remix import PlannerProfileData, PlannerVariant
from .sources.d4data import D4DataLookup


def _readable_paragon_board_name(
    board_id: str, lookup: D4DataLookup | None
) -> str:
    if lookup:
        n = lookup.paragon_board_name_for(board_id)
        if n:
            return n
    return board_id.replace("Paragon_", "").replace("_", " ")


def _readable_rune_name(rune_id: str, lookup: D4DataLookup | None) -> str:
    if not rune_id:
        return ""
    if lookup:
        n = lookup.rune_name_for(rune_id)
        if n:
            return n
    return humanize_key(rune_id)


def _readable_enchants(
    variant: PlannerVariant | None, lookup: D4DataLookup | None
) -> list[str]:
    if not variant:
        return []
    out: list[str] = []
    for raw in variant.enchants:
        sid = str(raw)
        # Parse '<Class>_Enchantment_<Skill>' -> '<Skill> Enchantment'.
        m = re.match(r"^[^_]+_Enchantment_(.+)$", sid)
        if m:
            skill = m.group(1)
            spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", skill)
            out.append(f"{spaced} Enchantment")
            continue
        if lookup:
            n = lookup.power_name_for(sid)
            if n:
                out.append(n)
                continue
        out.append(humanize_key(sid))
    return out


_ITEM_SLOT_PREFIXES = (
    "Helm_",
    "Chest_",
    "Gloves_",
    "Pants_",
    "Boots_",
    "Amulet_",
    "Ring_",
    "1HMace_",
    "1HSword_",
    "1HAxe_",
    "1HDagger_",
    "Wand_",
    "Focus_",
    "Shield_",
    "Totem_",
    "2HAxe_",
    "2HSword_",
    "2HMace_",
    "2HPolearm_",
    "2HScythe_",
    "2HStaff_",
    "Staff_",
    "Polearm_",
    "Bow_",
    "Crossbow_",
)


def _is_unique_template_affix_key(key: str) -> bool:
    """Affix keys like 'Helm_Unique_Generic_002' are unique-power templates.

    Their displayed text is the item's flavor power, not a separate affix
    string — labelling them with the raw key reads as a bug to the player.
    """
    return any(key.startswith(p) for p in _ITEM_SLOT_PREFIXES) and "_Unique_" in key


def _readable_affix_label(
    raw_key: str, raw_nid: int, lookup: D4DataLookup | None
) -> str:
    """Best-effort English label for an item affix (with d4data + humanizer)."""
    key = raw_key
    if not key and lookup and raw_nid:
        key = lookup.affix_key_for(raw_nid) or ""
    if not key:
        return f"affix #{raw_nid}" if raw_nid else "(unknown affix)"
    if _is_unique_template_affix_key(key):
        return "Unique Power"
    return humanize_key(key) or key


_VARIANT_PRIORITY = ("Mythic", "Ancestral", "Endgame", "Starter", "Leveling")
_PROGRESSION_VARIANT_PRIORITY = ("Skill Progression", "Leveling", "Starter")


def _pick_endgame_variant(profile: PlannerProfileData) -> PlannerVariant | None:
    by_name = {v.name: v for v in profile.variants}
    for n in _VARIANT_PRIORITY:
        if n in by_name and by_name[n].items:
            return by_name[n]
    return next(
        (v for v in profile.variants if v.items),
        profile.variants[0] if profile.variants else None,
    )


def _pick_skill_progression_variant(
    profile: PlannerProfileData,
) -> PlannerVariant | None:
    """Variant whose skillTree.steps best describe allocation order.

    Prefer 'Skill Progression' or 'Leveling' (which include multiple named
    milestones); fall back to whichever has the most skill-tree steps.
    """
    by_name = {v.name: v for v in profile.variants}
    for n in _PROGRESSION_VARIANT_PRIORITY:
        v = by_name.get(n)
        if v and len(v.skill_tree.get("steps", [])) >= 2:
            return v
    # Fall back: variant with the most skill-tree steps.
    by_step_count = sorted(
        profile.variants,
        key=lambda v: len(v.skill_tree.get("steps", [])),
        reverse=True,
    )
    return by_step_count[0] if by_step_count else None


def _resolve_node_label(
    class_slug: str,
    node_id: str,
    lookup: D4DataLookup | None,
) -> str:
    """Resolve a planner node ID to a readable name. d4data wins, YAML is fallback."""
    if lookup:
        n = lookup.skill_node_label_for(class_slug, node_id)
        if n:
            return n
    return _node_override_for(class_slug, node_id)


def _build_skill_tree_steps(
    variant: PlannerVariant | None,
    class_slug: str = "",
    lookup: D4DataLookup | None = None,
) -> list[SkillTreeStep]:
    if not variant or not variant.skill_tree:
        return []
    raw_steps = variant.skill_tree.get("steps", []) or []
    out: list[SkillTreeStep] = []
    prev_total = 0
    for i, step in enumerate(raw_steps, start=1):
        data = step.get("data") or {}
        if not isinstance(data, dict):
            continue
        nonzero = {k: int(v) for k, v in data.items() if int(v) > 0}
        total_points = sum(nonzero.values())
        node_ids = sorted(nonzero.keys(), key=lambda k: int(k))
        node_labels = [_resolve_node_label(class_slug, nid, lookup) for nid in node_ids]
        out.append(
            SkillTreeStep(
                order=i,
                name=str(step.get("name", f"Step {i}")),
                nodes_active=len(nonzero),
                total_points=total_points,
                points_added=max(total_points - prev_total, 0),
                node_ids=node_ids,
                node_labels=node_labels,
            )
        )
        prev_total = total_points
    return out


def _build_skill_point_clicks(
    variant: PlannerVariant | None,
    class_slug: str = "",
    lookup: D4DataLookup | None = None,
) -> list[SkillPointClick]:
    """Flatten step-checkpoints into a per-level "click here" allocation order.

    The planner gives us cumulative end-state at each named step (e.g. by
    "lvl 9 Eviscerate" the tree is `{node_a: 2, node_b: 1, ...}`). Between
    consecutive steps we compute the rank-delta per node and emit one click
    per added rank.

    Within a step we order clicks by `node_id` ascending — a heuristic that
    roughly tracks D4's tree-tier order (Basic = lowest IDs, then Core,
    Defensive, Mastery, Ultimate). For mapped names with explicit tier
    keywords we keep the basic-first ordering even more reliably. The level
    each click happens at is inferred from the step's *end-level* parsed from
    its name (e.g. "lvl 9 Eviscerate" -> end-level 9), distributing the
    points-added evenly across the levels gained since the previous step.
    """
    if not variant or not variant.skill_tree:
        return []
    raw_steps = variant.skill_tree.get("steps", []) or []
    if not raw_steps:
        return []

    out: list[SkillPointClick] = []
    prev_ranks: dict[str, int] = {}
    prev_total = 0
    prev_end_level = 0  # character level at the end of the previous step
    point_n = 0

    for step in raw_steps:
        data = step.get("data") or {}
        if not isinstance(data, dict):
            continue
        cur_ranks = {k: int(v) for k, v in data.items() if int(v) > 0}
        added: list[tuple[str, int]] = []
        for node_id, rank in cur_ranks.items():
            delta = rank - prev_ranks.get(node_id, 0)
            for r in range(prev_ranks.get(node_id, 0) + 1, rank + 1):
                added.append((node_id, r))
        # Stable, basic-first heuristic: order by integer node id ascending.
        added.sort(key=lambda nr: (int(nr[0]), nr[1]))

        cur_total = sum(cur_ranks.values())
        points_added = max(cur_total - prev_total, 0)
        # Determine end-level for this step from the name; fallback to a
        # 1-point-per-level cadence anchored at level 2.
        step_name = str(step.get("name", ""))
        m = re.search(r"\b(?:lvl|level)\s*(\d+)\b", step_name, flags=re.I)
        if m:
            end_level = int(m.group(1))
        elif prev_end_level == 0:
            # First step; assume final level == cumulative points + 1
            end_level = max(cur_total + 1, 2)
        else:
            end_level = prev_end_level + points_added

        # Spread added clicks across levels prev_end_level+1 .. end_level.
        levels_available = max(end_level - prev_end_level, points_added)
        for i, (node_id, new_rank) in enumerate(added):
            point_n += 1
            level = (
                prev_end_level
                + 1
                + min(i, max(levels_available - 1, 0))
            )
            label = (
                _resolve_node_label(class_slug, node_id, lookup)
                if class_slug
                else ""
            )
            out.append(
                SkillPointClick(
                    level=level,
                    point_number=point_n,
                    node_id=node_id,
                    node_label=label,
                    new_rank=new_rank,
                    step_name=step_name,
                    cumulative_total=prev_total + i + 1,
                )
            )

        prev_ranks = cur_ranks
        prev_total = cur_total
        prev_end_level = end_level

    return out


def _is_unique_item_id(item_id_str: str) -> bool:
    """Maxroll item ids are like 'Chest_Unique_Sorc_002' or 'Amulet_Legendary_Generic_001'.
    Uniques contain '_Unique_' in the id. """
    return "_Unique_" in item_id_str


def _humanize_skill_id(skill_id: str) -> str:
    """Sorcerer_IceShards -> 'Ice Shards'; X1_Sorcerer_Familiar -> 'Familiar'."""
    parts = skill_id.split("_")
    # Drop class prefix and X1/X2 generation prefixes
    keep = [p for p in parts if p not in ("X1", "X2") and p not in (
        "Sorcerer", "Barbarian", "Druid", "Necromancer", "Rogue", "Spiritborn"
    )]
    name = "".join(keep) if keep else skill_id
    # CamelCase -> spaced words
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)


def _humanize_item_pool_entry(
    pool_entry: dict,
    lookup: D4DataLookup | None = None,
) -> str:
    """Prefer d4data display name, then the item's `name` (legendaries),
    else derive from `id`."""
    raw = pool_entry.get("id", "")
    if lookup and raw:
        resolved = lookup.name_for(raw)
        if resolved:
            return resolved
    n = pool_entry.get("name")
    if n:
        return n
    if not raw:
        return "(unknown item)"
    return raw.replace("_", " ")


def _slot_from_item_id(item_id: str) -> GearSlot:
    """Derive the D4 gear slot from the leading token of a Maxroll item id.

    Item ids look like 'Helm_Unique_Sorc_002', '1HMace_Unique_Sorc_100',
    'Pants_Legendary_Generic_001'. The first token is the slot type and is
    stable across builds, unlike the planner's numeric slot index.
    """
    if not item_id:
        return GearSlot.OFFHAND
    prefix = item_id.split("_", 1)[0].lower()
    table = {
        "helm": GearSlot.HELM,
        "chest": GearSlot.CHEST,
        "gloves": GearSlot.GLOVES,
        "pants": GearSlot.PANTS,
        "boots": GearSlot.BOOTS,
        "amulet": GearSlot.AMULET,
        "ring": GearSlot.RING_1,
        "1hmace": GearSlot.WEAPON_1H_A,
        "1hsword": GearSlot.WEAPON_1H_A,
        "1haxe": GearSlot.WEAPON_1H_A,
        "1hdagger": GearSlot.WEAPON_1H_A,
        "wand": GearSlot.WEAPON_1H_A,
        "focus": GearSlot.OFFHAND,
        "shield": GearSlot.OFFHAND,
        "totem": GearSlot.OFFHAND,
        "2haxe": GearSlot.WEAPON_2H,
        "2hsword": GearSlot.WEAPON_2H,
        "2hmace": GearSlot.WEAPON_2H,
        "2hpolearm": GearSlot.WEAPON_2H,
        "2hscythe": GearSlot.WEAPON_2H,
        "2hstaff": GearSlot.WEAPON_2H,
        "staff": GearSlot.WEAPON_2H,
        "polearm": GearSlot.WEAPON_2H,
        "bow": GearSlot.RANGED,
        "crossbow": GearSlot.RANGED,
    }
    return table.get(prefix, GearSlot.OFFHAND)


def _build_skills(
    skill_names: list[str],
    variant: PlannerVariant | None,
    class_id: str,
) -> list[Skill]:
    """Use search_metadata names if present; otherwise derive from skillBar IDs."""
    if skill_names:
        return [
            Skill(id=10000 + i, class_id=class_id, name=name, tags=set(), ranks=1)
            for i, name in enumerate(skill_names)
        ]
    if not variant or not variant.skill_bar:
        return []
    return [
        Skill(
            id=10000 + i,
            class_id=class_id,
            name=_humanize_skill_id(sid),
            tags=set(),
            ranks=1,
        )
        for i, sid in enumerate(variant.skill_bar)
    ]


def _extract_item_affixes(
    pool_entry: dict,
    lookup: D4DataLookup | None = None,
) -> tuple[list[ItemAffix], list[ItemAffix], list[ItemAffix], int]:
    """Pull (implicits, explicits, tempered, greater_count) from a pool entry."""
    def to_affix(raw: dict, source: str) -> ItemAffix:
        nid = raw.get("nid") or 0
        try:
            nid = int(nid)
        except (TypeError, ValueError):
            nid = 0
        values = raw.get("values") or []
        value = float(values[0]) if values else 0.0
        key = ""
        if lookup and nid:
            key = lookup.affix_key_for(nid) or ""
        label = _readable_affix_label(key, nid, lookup)
        return ItemAffix(
            nid=nid,
            key=key,
            label=label,
            value=value,
            source=source,
            greater=bool(raw.get("greater")),
            upgrade=int(raw.get("upgrade", 0) or 0),
        )

    implicits = [to_affix(a, "implicit") for a in (pool_entry.get("implicits") or [])]
    explicits = [to_affix(a, "explicit") for a in (pool_entry.get("explicits") or [])]
    tempered = [to_affix(a, "tempered") for a in (pool_entry.get("tempered") or [])]
    greater_count = sum(1 for a in explicits if a.greater)
    return implicits, explicits, tempered, greater_count


def _extract_aspect(
    pool_entry: dict, lookup: D4DataLookup | None = None
) -> tuple[str, str]:
    """Return (aspect_id, aspect_name)."""
    aspects = pool_entry.get("aspects") or []
    if not aspects:
        return "", ""
    first = aspects[0]
    if isinstance(first, dict):
        aspect_id = str(first.get("id") or first.get("name") or "")
    else:
        aspect_id = str(first)
    aspect_name = ""
    if aspect_id and lookup:
        aspect_name = lookup.name_for(aspect_id) or lookup.power_name_for(aspect_id) or ""
    if not aspect_name and aspect_id:
        aspect_name = humanize_key(aspect_id)
    return aspect_id, aspect_name


def _extract_sockets(
    pool_entry: dict, lookup: D4DataLookup | None = None
) -> tuple[int, list[str]]:
    raw = pool_entry.get("sockets") or []
    if isinstance(raw, list):
        names: list[str] = []
        for s in raw:
            if not s:
                continue
            sid = str(s)
            label = _readable_rune_name(sid, lookup)
            names.append(label or sid)
        return len(raw), names
    if isinstance(raw, int):
        return raw, []
    return 0, []


def _build_items(
    skill_meta_items: list[str],
    variant: PlannerVariant | None,
    items_pool: dict,
    lookup: D4DataLookup | None = None,
    class_slug: str = "",
) -> dict[GearSlot, Item]:
    """Slot map -> Item. Names: d4data lookup > search_metadata > pool fallback.

    When d4data is available we prefer its canonical display name over
    Maxroll's `search_metadata` because (a) it's authoritative, and (b) the
    metadata list isn't slot-aligned and pairs by index, which can mis-name.
    """
    out: dict[GearSlot, Item] = {}
    if not variant:
        for i, name in enumerate(skill_meta_items):
            slot = list(GearSlot)[i % len(GearSlot)]
            out[slot] = Item(slot=slot, name=name, is_unique=False)
        return out

    slot_pairs = sorted(variant.items.items(), key=lambda kv: int(kv[0]))
    used_slots: set[GearSlot] = set()
    for i, (_, item_id) in enumerate(slot_pairs):
        pool_entry = items_pool.get(str(item_id), {})
        gear_slot = _slot_from_item_id(pool_entry.get("id", ""))
        if gear_slot == GearSlot.RING_1 and gear_slot in used_slots:
            gear_slot = GearSlot.RING_2
        elif gear_slot == GearSlot.WEAPON_1H_A and gear_slot in used_slots:
            gear_slot = GearSlot.WEAPON_1H_B

        # Resolution order: d4data > search_metadata > pool fallback.
        resolved = None
        raw_id = pool_entry.get("id", "")
        if lookup and raw_id:
            resolved = lookup.name_for(raw_id)
        if resolved is None and i < len(skill_meta_items):
            resolved = skill_meta_items[i]
        if not resolved:
            resolved = _humanize_item_pool_entry(pool_entry, lookup)

        is_unique = _is_unique_item_id(raw_id)
        implicits, explicits, tempered, greater_count = _extract_item_affixes(
            pool_entry, lookup
        )
        aspect_id, aspect_name = _extract_aspect(pool_entry, lookup)
        socket_count, sockets = _extract_sockets(pool_entry, lookup)
        out[gear_slot] = Item(
            slot=gear_slot,
            name=resolved,
            is_unique=is_unique,
            pool_id=raw_id,
            power=int(pool_entry.get("power", 0) or 0),
            upgrade=int(pool_entry.get("upgrade", 0) or 0),
            implicits=implicits,
            explicits=explicits,
            tempered=tempered,
            aspect_id=aspect_id,
            aspect_name=aspect_name,
            socket_count=socket_count,
            sockets=sockets,
            greater_affix_count=greater_count,
            suggested_affixes=suggested_affixes_for(gear_slot, class_slug),
            tempering=tempering_for(gear_slot),
            masterwork_priority=[masterwork_target_for(gear_slot)],
        )
        used_slots.add(gear_slot)
    return out


def _build_paragon(
    variant: PlannerVariant | None,
    lookup: D4DataLookup | None = None,
) -> list[ParagonBoard]:
    if not variant or not variant.paragon:
        return []
    boards: list[ParagonBoard] = []
    seen: set[str] = set()
    steps = variant.paragon.get("steps", [])
    placement = 0
    for step in steps:
        for entry in step.get("data", []) or []:
            board_id = entry.get("id", "")
            if not board_id or board_id in seen:
                continue
            seen.add(board_id)
            placement += 1
            boards.append(
                ParagonBoard(
                    id=board_id,
                    name=_readable_paragon_board_name(board_id, lookup),
                    placement_order=placement,
                )
            )
    return boards


def _build_paragon_steps(
    variant: PlannerVariant | None,
    lookup: D4DataLookup | None = None,
) -> list[ParagonStep]:
    """Extract progression milestones with per-board node counts and glyphs.

    Each entry under `paragon.steps[i].data` is one board state at that step:
        {
          "id": "Paragon_Sorc_00",
          "nodes": {"10": 1, "31": 1, ...}   # node_id -> rank
          "glyph": {"id": "Glyph_...", "rank": 21}     (optional)
        }

    We summarize each board as a ParagonBoardSnapshot so the report can show
    "Step 1 (Board Rush): Sorc 00 — 21 nodes; Sorc 01 — 14 nodes (glyph: ...)".
    """
    if not variant or not variant.paragon:
        return []
    steps_raw = variant.paragon.get("steps", []) or []
    out: list[ParagonStep] = []
    for i, step in enumerate(steps_raw, start=1):
        board_snapshots: list[ParagonBoardSnapshot] = []
        total_points = 0
        for entry in step.get("data", []) or []:
            board_id = entry.get("id", "")
            if not board_id:
                continue
            nodes = entry.get("nodes") or {}
            node_count = sum(int(v) for v in nodes.values())
            total_points += node_count
            glyph_raw = entry.get("glyph")
            glyph_level_raw = entry.get("glyphLevel")
            if isinstance(glyph_raw, dict):
                glyph_id = str(glyph_raw.get("id", ""))
                glyph_name = str(glyph_raw.get("name", ""))
                glyph_rank = int(glyph_raw.get("rank", 0) or 0)
            elif isinstance(glyph_raw, str):
                glyph_id = glyph_raw
                glyph_name = ""
                glyph_rank = 0
            else:
                glyph_id = glyph_name = ""
                glyph_rank = 0
            if glyph_id and not glyph_name and lookup:
                resolved = lookup.glyph_name_for(glyph_id)
                if resolved:
                    glyph_name = resolved
            if not glyph_name and glyph_id:
                glyph_name = glyph_id.replace("_", " ")
            if glyph_level_raw and not glyph_rank:
                try:
                    glyph_rank = int(glyph_level_raw)
                except (TypeError, ValueError):
                    pass
            sorted_nids = sorted(nodes.keys(), key=lambda k: int(k))
            node_labels = [
                lookup.paragon_node_label_for(board_id, nid) if lookup else ""
                for nid in sorted_nids
            ]
            board_snapshots.append(
                ParagonBoardSnapshot(
                    board_id=board_id,
                    board_name=_readable_paragon_board_name(board_id, lookup),
                    node_count=node_count,
                    node_ids=sorted_nids,
                    node_labels=node_labels,
                    glyph_id=glyph_id,
                    glyph_name=glyph_name,
                    glyph_rank=glyph_rank,
                    rotation=int(entry.get("rotation", 0) or 0),
                )
            )
        out.append(
            ParagonStep(
                order=i,
                name=str(step.get("name", f"Step {i}")),
                boards=board_snapshots,
                total_points=total_points,
            )
        )
    return out


def _stat_priorities_from_meta(meta: GuideMeta) -> list[StatPriority]:
    """Light extraction of stat priorities from guide section text.

    For v1 we punt and leave the list empty unless the section has terse cues.
    The full version will parse a structured Stat Priority widget once we
    handle that section.
    """
    return []


def reconcile(
    meta: GuideMeta,
    profile: PlannerProfileData,
    *,
    guide_url: str = "",
    tier: str = "S",
    d4data: D4DataLookup | None = None,
) -> Build:
    cls_slug = profile.class_name.lower()
    cls = GameClass(id=cls_slug, name=profile.class_name, slug=cls_slug)
    progression_variant = _pick_skill_progression_variant(profile)

    # Score every variant; pick the best by composite as the report's chosen build.
    scores = score_all_variants(profile.variants, profile.items_pool)
    best_name = best_variant_name(scores)
    by_name = {v.name: v for v in profile.variants}
    variant = (
        by_name.get(best_name)
        or _pick_endgame_variant(profile)
    )

    return Build(
        id=profile.id,
        **{"class": cls},
        archetype=meta.archetype or profile.name,
        tier=tier,
        role=meta.role or "Endgame",
        skills_in_order=_build_skills(profile.skill_names, variant, cls.id),
        skill_tree_steps=_build_skill_tree_steps(
            progression_variant or variant, cls.id, d4data
        ),
        skill_point_clicks=_build_skill_point_clicks(
            progression_variant or variant, cls.id, d4data
        ),
        enchants=_readable_enchants(variant, d4data),
        gear=_build_items(
            profile.item_names, variant, profile.items_pool, d4data, cls.id
        ),
        paragon_path=_build_paragon(variant, d4data),
        paragon_steps=_build_paragon_steps(variant, d4data),
        stat_priorities=_stat_priorities_from_meta(meta),
        variant_scores=scores,
        chosen_variant=variant.name if variant else "",
        season=meta.season or profile.season,
        source_urls={
            "guide": guide_url,
            "planner": maxroll_planner_url(profile.id),
        },
        planner_id=profile.id,
        fetched_at=datetime.now(timezone.utc),
        rotation_prose=meta.sections.get("Skill Rotation", ""),
    )
