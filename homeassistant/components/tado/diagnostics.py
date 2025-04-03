"""Provides diagnostics for Advantage Air."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import TadoConfigEntry

TO_REDACT = [
    "dealerPhoneNumber",
    "latitude",
    "logoPIN",
    "longitude",
    "postCode",
    "rid",
    "deviceNames",
    "deviceIds",
    "deviceIdsV2",
    "backupId",
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: TadoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = config_entry.runtime_data.coordinator.data
    mobile_devices = config_entry.runtime_data.mobile_coordinator

    return {
        "device": data.get("device"),
        "weather": data.get("weather"),
        "geofence": data.get("geofence"),
        "zone": data.get("zone"),
        "mobile_devices": mobile_devices.data,
    }
