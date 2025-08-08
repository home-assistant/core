"""Diagnostics support for Lunatone integration."""

from typing import Any, Final

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import LunatoneConfigEntry

TO_REDACT: Final[list[str]] = []


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LunatoneConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": {
            "info": entry.runtime_data.coordinator_info.data.model_dump(),
            "devices": [
                v.data.model_dump()
                for v in entry.runtime_data.coordinator_devices.data.values()
            ],
        },
    }
