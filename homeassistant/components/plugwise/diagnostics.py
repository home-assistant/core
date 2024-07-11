"""Diagnostics support for Plugwise."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import PlugwiseConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PlugwiseConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "gateway": coordinator.data.gateway,
        "devices": coordinator.data.devices,
    }
