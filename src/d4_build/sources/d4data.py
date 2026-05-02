"""Resolve Maxroll's internal item IDs to display names via d4data.

d4data is `DiabloTools/d4data`, a community-maintained datamine of Blizzard's
game data. It's a 4.6 GB git repo, but the lookups we need touch only the
localized StringList directory (~tens of MB) and the affix-definition
directory (~100 MB) — and we cache the affix-nid index so the second run
needs only the StringList files.

If d4data isn't installed, every lookup returns None — callers must fall
back gracefully.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import cache_dir


class D4DataLookup:
    """Lazy, file-backed display-name resolver."""

    def __init__(self, d4data_root: Path | None = None) -> None:
        self.d4data_root = Path(d4data_root) if d4data_root else default_d4data_root()
        self._memo: dict[str, str | None] = {}
        self._affix_nid_index: dict[int, str] | None = None
        self._skill_kit_cache: dict[str, dict[int, str]] = {}
        self._paragon_board_cache: dict[str, list[str]] = {}

    @property
    def stringlist_dir(self) -> Path:
        return self.d4data_root / "json" / "enUS_Text" / "meta" / "StringList"

    @property
    def affix_dir(self) -> Path:
        return self.d4data_root / "json" / "base" / "meta" / "Affix"

    @property
    def skill_kit_dir(self) -> Path:
        return self.d4data_root / "json" / "base" / "meta" / "SkillKit"

    @property
    def paragon_board_dir(self) -> Path:
        return self.d4data_root / "json" / "base" / "meta" / "ParagonBoard"

    def is_available(self) -> bool:
        return self.stringlist_dir.exists()

    def _affix_index_cache_path(self) -> Path:
        return cache_dir() / "affix_nid_index.json"

    def _load_affix_index(self) -> dict[int, str]:
        """Build (or load cached) nid -> affix-key map.

        First call walks the Affix directory (~1s, ~4500 entries). Subsequent
        calls hit the JSON cache.
        """
        if self._affix_nid_index is not None:
            return self._affix_nid_index

        cache_file = self._affix_index_cache_path()
        if cache_file.exists():
            try:
                self._affix_nid_index = {
                    int(k): v for k, v in json.loads(cache_file.read_text()).items()
                }
                return self._affix_nid_index
            except (OSError, json.JSONDecodeError, ValueError):
                pass

        if not self.affix_dir.exists():
            self._affix_nid_index = {}
            return self._affix_nid_index

        index: dict[int, str] = {}
        for path in self.affix_dir.glob("*.aff.json"):
            try:
                d = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            nid = d.get("__snoID__")
            if isinstance(nid, int):
                index[nid] = path.name[: -len(".aff.json")]
        self._affix_nid_index = index
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(index))
        except OSError:
            pass
        return index

    def affix_key_for(self, nid: int) -> str | None:
        """Return the d4data affix key for an SNO ID, or None."""
        if not isinstance(nid, int):
            return None
        return self._load_affix_index().get(nid)

    def _load_skill_kit_node_map(self, class_slug: str) -> dict[int, str]:
        """Build (and cache) the dwID -> gbidReward.name map for a class's SkillKit.

        SkillKit files live at `base/meta/SkillKit/<Class>.skl.json`. Each node
        in `arNodes` carries a `dwID` (the same numeric ID Maxroll's planner
        uses) and a `gbidReward.name` (the internal codename like
        'Warlock_Defensive_AbyssDemon1').
        """
        cache_key = class_slug.lower()
        if cache_key in self._skill_kit_cache:
            return self._skill_kit_cache[cache_key]

        if not self.is_available():
            self._skill_kit_cache[cache_key] = {}
            return {}

        # SkillKit filenames are TitleCase, e.g. Warlock.skl.json
        path = self.skill_kit_dir / f"{class_slug.title()}.skl.json"
        if not path.exists():
            self._skill_kit_cache[cache_key] = {}
            return {}

        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            self._skill_kit_cache[cache_key] = {}
            return {}

        node_map: dict[int, str] = {}
        for node in data.get("arNodes", []) or []:
            nid = node.get("dwID")
            gbid = node.get("gbidReward")
            if isinstance(nid, int) and isinstance(gbid, dict):
                name = gbid.get("name")
                if isinstance(name, str) and name:
                    node_map[nid] = name
        self._skill_kit_cache[cache_key] = node_map
        return node_map

    def _load_paragon_board_cells(self, board_id: str) -> list[str]:
        """Return a 441-entry list mapping cell-index -> ParagonNode codename.

        Empty cells return "" in the list.
        """
        if board_id in self._paragon_board_cache:
            return self._paragon_board_cache[board_id]

        if not self.is_available():
            self._paragon_board_cache[board_id] = []
            return []

        path = self.paragon_board_dir / f"{board_id}.pbd.json"
        if not path.exists():
            self._paragon_board_cache[board_id] = []
            return []

        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            self._paragon_board_cache[board_id] = []
            return []

        cells: list[str] = []
        for entry in data.get("arEntries", []) or []:
            if isinstance(entry, dict):
                cells.append(str(entry.get("name", "")))
            else:
                cells.append("")
        self._paragon_board_cache[board_id] = cells
        return cells

    def paragon_node_at(self, board_id: str, cell_index: int | str) -> str:
        """Codename of the ParagonNode at `arEntries[cell_index]` of a board.

        Returns "" if the board doesn't exist or the cell is empty.
        """
        try:
            idx = int(cell_index)
        except (TypeError, ValueError):
            return ""
        cells = self._load_paragon_board_cells(board_id)
        if 0 <= idx < len(cells):
            return cells[idx]
        return ""

    def paragon_node_label_for(self, board_id: str, cell_index: int | str) -> str:
        """Resolve a board+cell index to a readable name.

        Prefers the StringList display name (e.g. 'Overmind', 'Pyrosis').
        Falls back to a humanized codename for generic stat nodes
        (e.g. 'Generic_Normal_Str' -> 'Strength').
        """
        codename = self.paragon_node_at(board_id, cell_index)
        if not codename:
            return ""
        # Try StringList: ParagonNode_<codename>.stl.json
        n = self._lookup_with_prefixes(codename, ("ParagonNode_",))
        if n:
            return n
        return _humanize_paragon_node_codename(codename)

    def skill_node_label_for(self, class_slug: str, node_id: int | str) -> str:
        """Resolve a planner node ID to a humanized skill name.

        Returns "" if d4data isn't available or the class/node isn't found.
        Output examples:
            - 761 -> 'Abyss Demon (Defensive)'
            - 848 -> 'Abyss Demon (Core)'
            - 944 -> 'Demon 2 (Basic)'
            - 838 -> 'Abyss Sigil'
        """
        try:
            nid = int(node_id)
        except (TypeError, ValueError):
            return ""
        node_map = self._load_skill_kit_node_map(class_slug)
        gbid = node_map.get(nid)
        if not gbid:
            return ""
        return _humanize_skill_gbid(gbid)

    def name_for(self, item_id: str) -> str | None:
        """Return the display name for a Maxroll-style item id, or None."""
        return self._lookup_with_prefixes(item_id, ("Item_",))

    def glyph_name_for(self, glyph_id: str) -> str | None:
        """Display name for a paragon glyph ID like 'Rare_010_Dexterity_Main'."""
        return self._lookup_with_prefixes(
            glyph_id, ("Item_ParagonGlyph_", "ParagonGlyph_")
        )

    def paragon_board_name_for(self, board_id: str) -> str | None:
        """Display name for a paragon board ID like 'Paragon_Sorc_01' -> 'Searing Heat'."""
        return self._lookup_with_prefixes(board_id, ("ParagonBoard_",))

    def rune_name_for(self, rune_id: str) -> str | None:
        """Display name for a Rune ID like 'Rune_Condition_HitHealthierEnemy'."""
        return self._lookup_with_prefixes(rune_id, ("Item_", ""))

    def power_name_for(self, power_id: str) -> str | None:
        """Display name for skill / enchantment power IDs (case-insensitive fallback)."""
        direct = self._lookup_with_prefixes(power_id, ("Power_", ""))
        if direct:
            return direct
        # Maxroll planner sometimes uses camel-cased segments that don't match
        # d4data filename casing exactly (e.g. 'FireBall' vs 'Firebolt').
        if not self.is_available():
            return None
        # Case-insensitive directory scan, cached.
        cache_key = f"power_ci:{power_id.lower()}"
        if cache_key in self._memo:
            return self._memo[cache_key]
        target = f"Power_{power_id}.stl.json".lower()
        for entry in self.stringlist_dir.iterdir():
            if entry.name.lower() == target:
                try:
                    data = json.loads(entry.read_text())
                except (OSError, json.JSONDecodeError):
                    continue
                for s in data.get("arStrings", []) or []:
                    if s.get("szLabel") == "Name":
                        name = s.get("szText")
                        if isinstance(name, str) and name.strip():
                            self._memo[cache_key] = name
                            return name
        self._memo[cache_key] = None
        return None

    def _lookup_with_prefixes(
        self, raw_id: str, prefixes: tuple[str, ...]
    ) -> str | None:
        if not raw_id:
            return None
        cache_key = f"{prefixes}:{raw_id}"
        if cache_key in self._memo:
            return self._memo[cache_key]
        if not self.is_available():
            self._memo[cache_key] = None
            return None

        for prefix in prefixes:
            path = self.stringlist_dir / f"{prefix}{raw_id}.stl.json"
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            for entry in data.get("arStrings", []) or []:
                if entry.get("szLabel") == "Name":
                    name = entry.get("szText")
                    if isinstance(name, str) and name.strip():
                        self._memo[cache_key] = name
                        return name

        self._memo[cache_key] = None
        return None


def default_d4data_root() -> Path:
    return cache_dir() / "d4data"


_TIER_LABELS = {
    "Basic": "Basic",
    "Core": "Core",
    "Defensive": "Defensive",
    "Mastery": "Mastery",
    "Ultimate": "Ultimate",
    "Archfiend": "Archfiend",
    "Sigil": "Sigil",
    "Conjuration": "Conjuration",
    "Werebear": "Werebear",
    "Werewolf": "Werewolf",
    "Earth": "Earth",
    "Storm": "Storm",
    "Cold": "Cold",
    "Fire": "Fire",
    "Lightning": "Lightning",
    "Specialization": "Specialization",
    "Trap": "Trap",
    "Curse": "Curse",
    "Bone": "Bone",
    "Blood": "Blood",
    "Brawling": "Brawling",
    "Imbuement": "Imbuement",
    "Subterfuge": "Subterfuge",
}


_CLASS_PREFIXES = (
    "Warlock", "Sorcerer", "Barbarian", "Druid", "Necromancer",
    "Rogue", "Spiritborn", "Paladin",
)


_PARAGON_STAT_LABELS = {
    "Str": "Strength",
    "Int": "Intelligence",
    "Dex": "Dexterity",
    "Will": "Willpower",
    "Resource": "Resource",
    "Health": "Maximum Life",
    "Defense": "Defense",
    "Damage": "Damage",
    "Crit": "Critical",
    "Vuln": "Vulnerable",
    "Resist": "Resistance",
}


def _humanize_paragon_node_codename(codename: str) -> str:
    """`Generic_Normal_Str` -> 'Strength'; `Generic_Magic_Damage` -> 'Magic Damage Node'."""
    parts = codename.split("_")
    # Strip leading 'Generic'
    if parts and parts[0] == "Generic":
        parts = parts[1:]
    # Drop kind ('Normal' / 'Magic' / 'Rare' / 'Legendary' / 'Gate')
    kind = ""
    if parts and parts[0] in ("Normal", "Magic", "Rare", "Legendary", "Gate", "Socket"):
        kind = parts[0]
        parts = parts[1:]

    body = ""
    if parts:
        last = parts[-1]
        if last in _PARAGON_STAT_LABELS:
            body = _PARAGON_STAT_LABELS[last]
        else:
            body = " ".join(parts)
    if not body:
        return kind or codename

    if kind == "Gate":
        return "Gate"
    if kind == "Magic":
        return f"{body} (Magic)"
    if kind == "Rare":
        return f"{body} (Rare)"
    if kind == "Normal":
        # Normal stat nodes: 'Strength', 'Intelligence', etc. — body is enough.
        return body
    return body


def _humanize_skill_gbid(gbid: str) -> str:
    """Render a SkillKit gbid name into something readable.

    Example: `Warlock_Defensive_AbyssDemon1_Upgrade1` →
        'Abyss Demon 1 — Upgrade 1 (Defensive)'
    """
    import re

    parts = gbid.split("_")
    if parts and parts[0] in _CLASS_PREFIXES:
        parts = parts[1:]
    if not parts:
        return gbid

    tier = ""
    if parts[0] in _TIER_LABELS:
        tier = _TIER_LABELS[parts[0]]
        parts = parts[1:]

    upgrade_suffix = ""
    if parts and parts[-1].startswith("Upgrade"):
        upgrade_suffix = " — Upgrade " + parts[-1][len("Upgrade"):]
        parts = parts[:-1]

    body_tokens: list[str] = []
    for chunk in parts:
        spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", chunk)
        spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", spaced)
        body_tokens.extend(spaced.split())
    body = " ".join(body_tokens) if body_tokens else gbid
    if tier:
        return f"{body}{upgrade_suffix} ({tier})"
    return f"{body}{upgrade_suffix}"
