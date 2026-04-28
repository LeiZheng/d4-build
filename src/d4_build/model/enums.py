"""Enumerations for D4 build modeling.

DamageBucket categories follow the in-game multiplicative/additive structure.
References:
- https://maxroll.gg/d4/resources/in-depth-damage-guide
- https://mobalytics.gg/diablo-4/guides/damage-buckets-deep-dive
"""

from enum import Enum


class DamageBucket(str, Enum):
    ADDITIVE = "additive"
    VULNERABLE = "vulnerable"
    CRIT = "crit"
    OVERPOWER = "overpower"
    SKILL_TAG = "skill_tag"
    CONDITIONAL = "conditional"
    RESOURCE = "resource"
    OTHER = "other"


class GearSlot(str, Enum):
    HELM = "helm"
    CHEST = "chest"
    GLOVES = "gloves"
    PANTS = "pants"
    BOOTS = "boots"
    AMULET = "amulet"
    RING_1 = "ring_1"
    RING_2 = "ring_2"
    WEAPON_1H_A = "weapon_1h_a"
    WEAPON_1H_B = "weapon_1h_b"
    WEAPON_2H = "weapon_2h"
    OFFHAND = "offhand"
    RANGED = "ranged"
