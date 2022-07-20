"""Diagnostics support for Ridwell."""
from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import RidwellData
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: RidwellData = hass.data[DOMAIN][entry.entry_id]

    return {
        "data": [dataclasses.asdict(event) for event in data.coordinator.data.values()]
    }
