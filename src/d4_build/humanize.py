"""Humanize d4data keys to readable English when no display name is available.

Examples:
    'S04_LifePerHit' -> 'Life Per Hit'
    'UBERUNIQUE_LifeFlat_HarlequinCrest' -> 'Life Flat'
    'UNIQUE_INHERENT_PassiveRankBonus_Generic_All_ShroudOfFalseDeath' -> 'Passive Rank Bonus'
    'Rune_Condition_HitHealthierEnemy' -> 'Hit Healthier Enemy'
"""

from __future__ import annotations

import re

# Stripped from the FRONT, in order. Matched literally then trimmed.
_LEADING_PREFIXES: tuple[str, ...] = (
    "UBERUNIQUE_INHERENT_",
    "UNIQUE_INHERENT_",
    "UBERUNIQUE_",
    "UNIQUE_",
    "INHERENT_",
    "ITEM_",
    "Tempered_",
    "Rune_Condition_",
    "Rune_Effect_",
    "Rune_",
    "Power_",
    "Skill_",
    "Affix_",
    "S04_",
    "S05_",
    "S06_",
    "S07_",
    "S08_",
    "S09_",
    "S10_",
    "S11_",
    "S12_",
    "S13_",
)

# Stripped if present in the trailing tokens — these are names of unique items
# that get appended to affix keys so two uniques can share an affix template.
_KNOWN_UNIQUE_SUFFIXES: tuple[str, ...] = (
    "_HarlequinCrest",
    "_ShroudOfFalseDeath",
    "_Temerity",
    "_RingOfStarlessSkies",
    "_StaffOfEndlessRage",
    "_GlovesOfTheIlluminator",
    "_Generic",
    "_AllClasses",
    "_AllOperators",
)


def humanize_key(key: str) -> str:
    """Convert a d4data key into a readable English string.

    Best-effort. The result is intended as a fallback when the proper display
    name isn't available — it preserves enough information that a player can
    still recognize what the affix does.
    """
    if not key:
        return ""
    s = key
    for p in _LEADING_PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
            break

    # Strip trailing unique-name suffixes once (longest match first).
    for suffix in sorted(_KNOWN_UNIQUE_SUFFIXES, key=len, reverse=True):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break

    # snake_case → tokens; CamelCase → tokens.
    tokens: list[str] = []
    for chunk in re.split(r"[_]+", s):
        if not chunk:
            continue
        # Split CamelCase: insert space before each uppercase that follows a lowercase
        # or before an uppercase followed by lowercase.
        spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", chunk)
        spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", spaced)
        tokens.extend(spaced.split())

    if not tokens:
        return key

    # Drop leading bookkeeping tokens that aren't meaningful for the player.
    DROP = {"Generic", "All", "Class", "Classes"}
    while tokens and tokens[0] in DROP:
        tokens.pop(0)
    while tokens and tokens[-1] in DROP:
        tokens.pop()

    if not tokens:
        return key

    return " ".join(tokens)
