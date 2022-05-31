"""Define RainMachine utilities."""
from __future__ import annotations

from typing import Any


def key_exists(data: dict[str, Any], search_key: str) -> bool:
    """Return whether a key exists in a nested dict."""
    for key, value in data.items():
        if key == search_key:
            return True
        if isinstance(value, dict):
            return key_exists(value, search_key)
    return False
