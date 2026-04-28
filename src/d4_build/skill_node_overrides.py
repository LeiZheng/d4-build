"""Loader for the manual class -> node_id -> name override table.

This is a stopgap: when d4data ships an update with the relevant class skill
tree, the YAML's contribution becomes redundant and can be deleted. The
loader is forgiving — a missing or empty YAML returns an empty mapping, so
removing the file is safe.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


_DATA_PATH = Path(__file__).parent / "data" / "skill_node_overrides.yaml"


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, str]]:
    if not _DATA_PATH.exists():
        return {}
    raw = yaml.safe_load(_DATA_PATH.read_text()) or {}
    out: dict[str, dict[str, str]] = {}
    for cls, m in raw.items():
        if isinstance(m, dict):
            out[str(cls).lower()] = {str(k): str(v) for k, v in m.items()}
    return out


def label_for(class_slug: str, node_id: str) -> str:
    """Return the readable name for a node id, or empty string if no override."""
    if not class_slug or not node_id:
        return ""
    return _load().get(class_slug.lower(), {}).get(str(node_id), "")


def labels_for_class(class_slug: str) -> dict[str, str]:
    return dict(_load().get(class_slug.lower(), {}))
