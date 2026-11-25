"""Shared manifest sorting helpers."""

from typing import Any

_MANIFEST_SORT_KEYS = {"domain": ".domain", "name": ".name"}


def _sort_manifest_keys(key: str) -> str:
    """Sort manifest keys."""
    return _MANIFEST_SORT_KEYS.get(key, key)


def sort_manifest(manifest: dict[str, Any]) -> bool:
    """Sort manifest."""
    keys = list(manifest)
    if (keys_sorted := sorted(keys, key=_sort_manifest_keys)) != keys:
        sorted_manifest = {key: manifest[key] for key in keys_sorted}
        manifest.clear()
        manifest.update(sorted_manifest)
        return True

    return False
