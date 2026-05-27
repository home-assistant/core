"""Diagnostics support for the Data Grand Lyon integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import DataGrandLyonConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DataGrandLyonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator_data": {
            "stops": {
                subentry_id: [asdict(passage) for passage in passages]
                for subentry_id, passages in entry.runtime_data.tcl_coordinator.data.items()
            },
            "velov_stations": {
                subentry_id: asdict(station)
                for subentry_id, station in entry.runtime_data.velov_coordinator.data.items()
            },
        },
    }
