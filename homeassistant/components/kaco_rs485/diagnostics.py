"""Diagnostics support for the KACO RS485 integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .coordinator import KacoRs485ConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KacoRs485ConfigEntry
) -> dict[str, Any]:
    """Return the entry and each inverter's last known state."""
    inverters: dict[str, Any] = {}
    # Setup sets runtime_data only after the first poll succeeds.
    if entry.state is ConfigEntryState.LOADED:
        inverters = {
            str(address): asdict(state)
            for address, state in entry.runtime_data.data.items()
        }
    return {"entry_data": dict(entry.data), "inverters": inverters}
