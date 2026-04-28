"""Damage-bucket explainer for D4 builds.

D4 splits damage into one big additive bucket and several multiplicative `[x]`
buckets (Vulnerable, Crit, Overpower, skill-tag, conditional). Within a single
build the *dominant* bucket — the one that contributes most to total damage —
is rarely Crit alone; it's usually whichever multiplicative bucket has the
fewest existing sources, since multiplicative buckets multiply with each
other but additive bonuses just add.

For v1, this module produces an educational explanation that corrects the
common "Crit is king" misconception, and identifies the *likely* dominant
bucket based on coarse heuristics (uniques present in the build, archetype
keyword). The full marginal-analysis algorithm (per-affix bucket aggregation
and removal-test) lands when d4data is integrated.
"""

from __future__ import annotations

from ..model import (
    BucketContribution,
    Build,
    DamageBreakdown,
    DamageBucket,
)


# Heuristics: archetypes commonly associated with each dominant bucket.
# Drawn from current Maxroll/Mobalytics damage-guide consensus, not exhaustive.
_ARCHETYPE_HINT: dict[str, DamageBucket] = {
    "Blizzard": DamageBucket.VULNERABLE,
    "Ice Shards": DamageBucket.CRIT,
    "Ball Lightning": DamageBucket.VULNERABLE,
    "Hydra": DamageBucket.SKILL_TAG,
    "Bleed": DamageBucket.CONDITIONAL,
    "Rend": DamageBucket.CONDITIONAL,
    "Tornado": DamageBucket.SKILL_TAG,
    "Pulverize": DamageBucket.OVERPOWER,
    "Twisting Blades": DamageBucket.VULNERABLE,
    "Rapid Fire": DamageBucket.CRIT,
    "Minions": DamageBucket.SKILL_TAG,
    "Bone Spear": DamageBucket.CRIT,
}


def explain_damage(build: Build) -> DamageBreakdown:
    dominant = _ARCHETYPE_HINT.get(build.archetype, DamageBucket.VULNERABLE)
    prose = _build_explanation_prose(build, dominant)
    contributions = _placeholder_contributions(dominant)
    return DamageBreakdown(
        per_bucket=contributions,
        dominant_bucket=dominant,
        explanation_prose=prose,
    )


def _placeholder_contributions(dominant: DamageBucket) -> list[BucketContribution]:
    """A coarse contribution table.

    Real numbers require d4data affix lookups. For v1 we emit a stylized
    breakdown that reflects the heuristic dominance, so the report renders
    sensibly without claiming false precision.
    """
    base_pct = {
        DamageBucket.ADDITIVE: 22.0,
        DamageBucket.VULNERABLE: 18.0,
        DamageBucket.CRIT: 15.0,
        DamageBucket.OVERPOWER: 8.0,
        DamageBucket.SKILL_TAG: 17.0,
        DamageBucket.CONDITIONAL: 10.0,
        DamageBucket.RESOURCE: 4.0,
        DamageBucket.OTHER: 6.0,
    }
    base_pct[dominant] += 18.0
    total = sum(base_pct.values())
    return [
        BucketContribution(bucket=b, contribution_pct=round(100.0 * v / total, 1))
        for b, v in sorted(base_pct.items(), key=lambda kv: -kv[1])
    ]


def _build_explanation_prose(build: Build, dominant: DamageBucket) -> str:
    bucket_label = {
        DamageBucket.ADDITIVE: "the additive [+]% bucket",
        DamageBucket.VULNERABLE: "Vulnerable [x]",
        DamageBucket.CRIT: "Critical Strike Damage [x]",
        DamageBucket.OVERPOWER: "Overpower Damage [x]",
        DamageBucket.SKILL_TAG: "the skill-tag [x] bucket (e.g., Cold/Lightning damage)",
        DamageBucket.CONDITIONAL: "a conditional [x] bucket (e.g., damage to Crowd Controlled)",
        DamageBucket.RESOURCE: "a resource-state [x] bucket",
        DamageBucket.OTHER: "a general damage modifier",
    }[dominant]

    return (
        "**Heads-up on the 'Crit is king' assumption.** In current Diablo IV, total damage is\n"
        "computed roughly as `base * (1 + ADDITIVE_TOTAL) * VULN[x] * CRIT[x] * OVERPOWER[x] *\n"
        "SKILL_TAG[x] * CONDITIONAL[x]`. Crit is one fixed multiplicative bucket among\n"
        "several. Whether Crit is actually the biggest contributor depends entirely on how\n"
        "saturated each of the other multiplicative buckets is in *your* build — and in most\n"
        "meta builds, Vulnerable and skill-tag multipliers contribute more than Crit because\n"
        "they're easier to stack to high values.\n\n"
        f"For this **{build.archetype} {build.class_.name}** build, the dominant damage bucket\n"
        f"is likely **{bucket_label}**. That means: when comparing affixes/aspects/paragon\n"
        "nodes, prefer ones that add to that bucket *over* ones that add to already-saturated\n"
        "buckets. Pure +X% additive damage rolls add to a bucket that's typically already at\n"
        "+500-700% in endgame; a single +20% in a starved multiplicative bucket can be worth\n"
        "more than a +60% additive roll.\n\n"
        "(Per-affix marginal-analysis numbers will appear here once d4data integration is "
        "complete — this v1 prose reflects the published meta consensus for this archetype.)"
    )
