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

    @property
    def stringlist_dir(self) -> Path:
        return self.d4data_root / "json" / "enUS_Text" / "meta" / "StringList"

    @property
    def affix_dir(self) -> Path:
        return self.d4data_root / "json" / "base" / "meta" / "Affix"

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
