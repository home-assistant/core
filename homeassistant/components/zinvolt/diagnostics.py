"""Diagnostics support for Zinvolt."""

from __future__ import annotations

from dataclasses import asdict
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
                coordinator.battery.identifier: asdict(coordinator.data),
            }
            for coordinator in entry.runtime_data.values()
        ],
    }
