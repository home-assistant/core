"""Diagnostics support for Lunatone integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import LunatoneConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LunatoneConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "info": entry.runtime_data.coordinator_info.data.model_dump(),
        "devices": [
            v.data.model_dump()
            for v in entry.runtime_data.coordinator_devices.data.values()
        ],
    }
