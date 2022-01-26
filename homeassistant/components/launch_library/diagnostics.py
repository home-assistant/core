"""Diagnostics support for Launch Library."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import LaunchLibraryData
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator[LaunchLibraryData] = hass.data[DOMAIN]
    if coordinator.data is None:
        return {}
    next_launch = coordinator.data["upcoming_launches"][0]
    starship_launch = coordinator.data["starship_events"].upcoming.launches[0]
    return {
        "next_launch": next_launch.raw_data_contents,
        "starship": starship_launch.raw_data_contents,
    }
