"""Diagnostics support for RDW."""
from __future__ import annotations

import json
from typing import Any

from vehicle import Vehicle

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator[Vehicle] = hass.data[DOMAIN][entry.entry_id]
    # Round-trip via JSON to trigger serialization
    data: dict[str, Any] = json.loads(coordinator.data.json())
    return data
