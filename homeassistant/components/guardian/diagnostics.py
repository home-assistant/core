"""Diagnostics support for Guardian."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from . import GuardianData
from .const import CONF_UID, DOMAIN

CONF_BSSID = "bssid"
CONF_PAIRED_UIDS = "paired_uids"
CONF_SSID = "ssid"
CONF_TITLE = "title"

TO_REDACT = {
    CONF_BSSID,
    CONF_PAIRED_UIDS,
    CONF_SSID,
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
    CONF_UID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: GuardianData = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": {
            "valve_controller": {
                api_category: async_redact_data(coordinator.data, TO_REDACT)
                for api_category, coordinator in data.valve_controller_coordinators.items()
            },
            "paired_sensors": [
                async_redact_data(coordinator.data, TO_REDACT)
                for coordinator in data.paired_sensor_manager.coordinators.values()
            ],
        },
    }
