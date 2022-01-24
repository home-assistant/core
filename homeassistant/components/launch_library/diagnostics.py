"""Diagnostics support for Launch Library."""
from __future__ import annotations

from typing import Any

from pylaunches.objects.launch import Launch

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator[list[Launch]] = hass.data[DOMAIN]
    next_launch = coordinator.data[0] if coordinator.data else None
    return {
        "next_launch": next_launch.raw_data_contents if next_launch else None,
    }
