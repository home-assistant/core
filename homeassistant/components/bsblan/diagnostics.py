"""Diagnostics support for BSBLan."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import BSBLanData
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: BSBLanData = hass.data[DOMAIN][entry.entry_id]

    return {
        "info": await data.info.to_dict()
        if asyncio.iscoroutinefunction(data.info.to_dict)
        else data.info.to_dict(),
        "device": await data.device.to_dict()
        if asyncio.iscoroutinefunction(data.device.to_dict)
        else data.device.to_dict(),
        "coordinator_data": {
            "state": await data.coordinator.data.state.to_dict()
            if asyncio.iscoroutinefunction(data.coordinator.data.state.to_dict)
            else data.coordinator.data.state.to_dict(),
        },
    }
