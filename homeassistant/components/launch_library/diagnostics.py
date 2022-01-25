"""Diagnostics support for Launch Library."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, STARSHIP_EVENTS, UPCOMING_LAUNCHES


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator[dict[str, Any]] = hass.data[DOMAIN]
    next_launch = coordinator.data[UPCOMING_LAUNCHES][0] if coordinator.data else None
    starship_launch = (
        coordinator.data[STARSHIP_EVENTS].upcoming.launches[0]
        if coordinator.data
        else None
    )
    return {
        "next_launch": next_launch.raw_data_contents if next_launch else None,
        "starship_launch": starship_launch.raw_data_contents
        if starship_launch
        else None,
    }
