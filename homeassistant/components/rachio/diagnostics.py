"""Diagnostics support for Rachio."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .device import RachioConfigEntry

TO_REDACT = {
    "address",
    "baseStationId",
    "deviceId",
    "externalId",
    "id",
    "imageUrl",
    "latitude",
    "longitude",
    "macAddress",
    "programId",
    "serialNumber",
    "valveId",
    "zip",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RachioConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    person = entry.runtime_data
    return {
        "options": dict(entry.options),
        "controllers": [
            async_redact_data(controller.init_data, TO_REDACT)
            for controller in person.controllers
        ],
        "base_stations": [
            {
                "base_station": async_redact_data(
                    base.status_coordinator.base_station, TO_REDACT
                ),
                "valves": async_redact_data(
                    list(base.status_coordinator.data.values()), TO_REDACT
                ),
                "schedule": async_redact_data(
                    base.schedule_coordinator.data, TO_REDACT
                ),
            }
            for base in person.base_stations
        ],
    }
