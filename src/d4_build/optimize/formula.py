"""Walk every formula we have and compute a final-state CharacterStats.

This is the "compute final character data by all formulas" function. It uses
the data we already extract (item affixes, paragon node counts, skill tree
state, gear power, world tier) and the in-game formula structure documented
in CLAUDE.md.

Heuristic. Not in-game truth. See stats.py docstring for the honesty notes.
"""

from __future__ import annotations

from ..model import (
    Build,
    CharacterStats,
    DamageBucket,
)


# Per-bucket affix-keyword classifier. Reads affix labels (humanized d4data
# keys) and assigns to a bucket. Used when ItemAffix.bucket isn't populated
# directly (which is currently the common case until full d4data wiring).
_BUCKET_KEYWORDS = {
    DamageBucket.VULNERABLE: ("vulnerable",),
    DamageBucket.CRIT: ("crit", "critical"),
    DamageBucket.OVERPOWER: ("overpower",),
    DamageBucket.SKILL_TAG: (
        "fire", "cold", "lightning", "shadow", "physical",
        "abyss", "darkness", "burning", "frost",
    ),
    DamageBucket.CONDITIONAL: (
        "vulnerable", "crowd controlled", "crowd_controlled", "to elite",
        "to_elite", "to bosses", "to close", "to distant", "in shadowform",
    ),
    DamageBucket.RESOURCE: ("mana", "fury", "spirit", "essence", "energy", "resource"),
}


def _classify_affix(label: str) -> DamageBucket:
    s = (label or "").lower()
    for bucket, kws in _BUCKET_KEYWORDS.items():
        if any(kw in s for kw in kws):
            return bucket
    if "damage" in s or "+%" in s or "increase" in s:
        return DamageBucket.ADDITIVE
    return DamageBucket.OTHER


def compute_character_stats(build: Build) -> CharacterStats:
    """Walk every gear affix + paragon contribution + skill rank to a stat block.

    Heuristic categorization: we tag each affix by its readable label keywords
    (since `Affix.bucket` is rarely populated end-to-end yet). Bucket totals
    feed the multiplicative-bucket damage formula:
        D = base * (1 + ADDITIVE) * VULN * CRIT * OP * SKILL_TAG * CONDITIONAL
    """
    stats = CharacterStats()

    # 1. Walk every affix on every gear slot.
    for item in build.gear.values():
        for a in (item.implicits + item.explicits + item.tempered):
            label = a.label or a.key
            value = float(a.value or 0)
            # Greater-affix multiplier — empirical 5x scaling.
            if a.greater:
                value *= 5.0

            bucket = _classify_affix(label)
            if bucket == DamageBucket.ADDITIVE:
                stats.additive_damage_total += value
            elif bucket == DamageBucket.VULNERABLE:
                stats.vulnerable_multiplier += value / 100.0
            elif bucket == DamageBucket.CRIT:
                if "chance" in label.lower():
                    stats.lucky_hit_pct += value
                else:
                    stats.crit_multiplier += value / 100.0
            elif bucket == DamageBucket.OVERPOWER:
                stats.overpower_multiplier += value / 100.0
            elif bucket == DamageBucket.SKILL_TAG:
                stats.skill_tag_multiplier *= 1.0 + value / 100.0
            elif bucket == DamageBucket.CONDITIONAL:
                stats.conditional_multiplier *= 1.0 + value / 100.0
            elif bucket == DamageBucket.RESOURCE:
                stats.resource_generation_pct += value

            # Defensive contributions live in label-keyword space too.
            ll = label.lower()
            if "life" in ll and "regen" not in ll:
                stats.life_total += value
            elif "armor" in ll:
                stats.armor_total += value
            elif "damage reduction" in ll or "reduce damage" in ll:
                stats.damage_reduction_pct += value
            elif "cooldown" in ll:
                stats.cooldown_reduction_pct += value
            elif "lucky hit" in ll:
                stats.lucky_hit_pct += value

    # 2. Paragon contribution: each board's allocated points contribute via
    # generic stat nodes (~2 points per stat per board on average).
    paragon_total = sum(
        bs.node_count
        for step in build.paragon_steps
        for bs in step.boards
    ) if build.paragon_steps else 0
    if paragon_total:
        # Take the LAST step's totals as the final-state — earlier steps are
        # progression checkpoints.
        last_step = build.paragon_steps[-1]
        final_paragon_points = last_step.total_points
        # Each paragon point ~= 1 stat point on average → small additive boost.
        # Tuned conservatively.
        stats.life_total += final_paragon_points * 8.0  # rough str/will → life
        stats.armor_total += final_paragon_points * 1.0  # rough str → armor

    # 3. Skill ranks: every rank past 1 in a primary damage skill counts as
    # +25% additive multiplier (rough D4 baseline). Sum across all clicks.
    primary_ranks = 0
    for c in build.skill_point_clicks:
        if c.new_rank > 1:
            primary_ranks += 1
    stats.additive_damage_total += primary_ranks * 25.0

    # 4. Composite damage formula
    base_damage = 1000.0  # arbitrary unit; only ratios matter
    stats.representative_damage = (
        base_damage
        * (1.0 + stats.additive_damage_total / 100.0)
        * stats.vulnerable_multiplier
        * stats.crit_multiplier
        * stats.overpower_multiplier
        * stats.skill_tag_multiplier
        * stats.conditional_multiplier
    )

    # 5. EHP — life × DR factor × armor factor
    armor_dr = stats.armor_total / (stats.armor_total + 5 * 70 + 1500)  # level 70 approx
    dr_total = min(1.0 - (1.0 - stats.damage_reduction_pct / 100.0), 0.85)
    stats.effective_hp = max(stats.life_total, 1.0) * (1.0 + armor_dr) * (1.0 + dr_total)

    # 6. Sustain — CDR + resource gen + lucky hit
    cdr_factor = 1.0 / max(1.0 - min(stats.cooldown_reduction_pct, 70.0) / 100.0, 0.30)
    stats.sustained_dps_factor = (
        cdr_factor
        * (1.0 + stats.resource_generation_pct / 100.0)
        * (1.0 + stats.lucky_hit_pct / 200.0)
    )

    # 7. 0-100 score axes — normalize against pre-set targets.
    DAMAGE_TARGET = 60_000.0
    EHP_TARGET = 40_000.0
    SUSTAIN_TARGET = 4.0
    stats.damage_score = min(100.0, 100.0 * stats.representative_damage / DAMAGE_TARGET)
    stats.survive_score = min(100.0, 100.0 * stats.effective_hp / EHP_TARGET)
    stats.sustain_score = min(100.0, 100.0 * stats.sustained_dps_factor / SUSTAIN_TARGET)
    stats.composite_score = (
        0.5 * stats.damage_score
        + 0.3 * stats.survive_score
        + 0.2 * stats.sustain_score
    )

    return stats
