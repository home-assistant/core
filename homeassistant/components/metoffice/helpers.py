"""Helpers used for Met Office integration."""

from __future__ import annotations

from typing import Any


def get_attribute(data: dict[str, Any] | None, attr_name: str) -> Any | None:
    """Get an attribute from weather data."""
    if data:
        return data.get(attr_name, {}).get("value")
    return None
