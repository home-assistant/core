"""Diagnostics support for Weheat."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import WeheatConfigEntry

TO_REDACT = {"heat_pump_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WeheatConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "heat_pumps": [
            {
                "model": weheatdata.heat_pump_info.model,
                "has_dhw": weheatdata.heat_pump_info.has_dhw,
                "logs": async_redact_data(
                    weheatdata.data_coordinator.data.raw_content or {}, TO_REDACT
                ),
                "energy": async_redact_data(
                    weheatdata.energy_coordinator.data.raw_content or {}, TO_REDACT
                ),
            }
            for weheatdata in entry.runtime_data
        ]
    }
