"""Diagnostics support for the KACO RS485 integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import KacoRs485ConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KacoRs485ConfigEntry
) -> dict[str, Any]:
    """Return the entry and each inverter's last known state."""
    return {
        "entry_data": dict(entry.data),
        "inverters": {
            str(address): asdict(state)
            for address, state in entry.runtime_data.data.items()
        },
    }
