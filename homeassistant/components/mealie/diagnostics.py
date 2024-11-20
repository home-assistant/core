"""Diagnostics support for the Mealie integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from . import MealieConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MealieConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = config_entry.runtime_data

    about = await data.client.get_about()

    return {
        "about": asdict(about),
        "mealplans": {
            entry_type: [asdict(mealplan) for mealplan in mealplans]
            for entry_type, mealplans in data.mealplan_coordinator.data.items()
        },
        "shoppinglist": {
            list_id: asdict(shopping_list)
            for list_id, shopping_list in data.shoppinglist_coordinator.data.items()
        },
    }
