"""Diagnostics support for Guardian."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_UID, DATA_COORDINATOR, DATA_COORDINATOR_PAIRED_SENSOR, DOMAIN
from .util import GuardianDataUpdateCoordinator

CONF_BSSID = "bssid"
CONF_PAIRED_UIDS = "paired_uids"
CONF_SSID = "ssid"

TO_REDACT = {
    CONF_BSSID,
    CONF_PAIRED_UIDS,
    CONF_SSID,
    CONF_UID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    coordinators: dict[str, GuardianDataUpdateCoordinator] = data[DATA_COORDINATOR]
    paired_sensor_coordinators: dict[str, GuardianDataUpdateCoordinator] = data[
        DATA_COORDINATOR_PAIRED_SENSOR
    ]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "data": {
            "valve_controller": {
                api_category: async_redact_data(coordinator.data, TO_REDACT)
                for api_category, coordinator in coordinators.items()
            },
            "paired_sensors": [
                async_redact_data(coordinator.data, TO_REDACT)
                for coordinator in paired_sensor_coordinators.values()
            ],
        },
    }
