"""Utility functions for the scaffold script."""

import argparse
from typing import Any

from .const import COMPONENT_DIR


def valid_integration(integration):
    """Test if it's a valid integration."""
    if not (COMPONENT_DIR / integration).exists():
        raise argparse.ArgumentTypeError(
            f"The integration {integration} does not exist."
        )

    return integration


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
