"""Tests for the OurGroceries integration."""

from typing import Any


def items_to_shopping_list(
    items: list, version_id: str = "1"
) -> dict[str, dict[str, Any]]:
    """Convert a list of items into a shopping list."""
    return {"list": {"versionId": version_id, "items": items}}
