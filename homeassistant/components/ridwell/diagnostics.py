"""Diagnostics support for Ridwell."""
from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DATA_COORDINATOR, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    return {
        "data": [dataclasses.asdict(event) for event in coordinator.data.values()],
    }
