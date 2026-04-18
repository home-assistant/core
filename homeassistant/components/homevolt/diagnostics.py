"""Diagnostics support for Homevolt."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import HomevoltConfigEntry

TO_REDACT = {CONF_HOST, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomevoltConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    client = coordinator.data

    result: dict[str, Any] = {
        "config": async_redact_data(entry.data, TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
        },
    }
    if client is None:
        return result

    result["device"] = {
        "unique_id": client.unique_id,
    }
    result["sensors"] = {
        key: {"value": sensor.value, "type": sensor.type}
        for key, sensor in client.sensors.items()
    }
    result["ems"] = {
        device_id: {
            "name": metadata.name,
            "model": metadata.model,
            "sensors": {
                key: sensor.value
                for key, sensor in client.sensors.items()
                if sensor.device_identifier == device_id
            },
        }
        for device_id, metadata in client.device_metadata.items()
    }

    return result
