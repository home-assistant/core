"""Diagnostics support for Peblar."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import PeblarConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PeblarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "system_information": entry.runtime_data.system_information.to_dict(),
        "user_configuration": entry.runtime_data.user_configuraton_coordinator.data.to_dict(),
        "meter": entry.runtime_data.meter_coordinator.data.to_dict(),
        "versions": {
            "available": entry.runtime_data.version_coordinator.data.available.to_dict(),
            "current": entry.runtime_data.version_coordinator.data.current.to_dict(),
        },
    }
