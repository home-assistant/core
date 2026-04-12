"""Diagnostics support for Zinvolt."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import ZinvoltConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ZinvoltConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "coordinators": [
            {
                coordinator.battery.identifier: coordinator.data.to_dict(),
            }
            for coordinator in entry.runtime_data.values()
        ],
    }
