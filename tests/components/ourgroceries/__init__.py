"""Tests for the OurGroceries integration."""


def items_to_shopping_list(items: list) -> dict[dict[list]]:
    """Convert a list of items into a shopping list."""
    return {"list": {"items": items}}
