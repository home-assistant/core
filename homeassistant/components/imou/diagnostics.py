"""Diagnostics support for Imou."""

from typing import Any

from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_APP_SECRET, imou_device_identifier
from .coordinator import ImouConfigEntry

TO_REDACT = {CONF_APP_SECRET}


def _serialize_device(device: ImouHaDevice) -> dict[str, Any]:
    """Return a JSON-safe view of a discovered Imou device."""
    return {
        "identifier": imou_device_identifier(device),
        "device_id": device.device_id,
        "channel_id": device.channel_id,
        "model": device.model,
        "manufacturer": device.manufacturer,
        "sw_version": device.swversion,
        "product_id": device.product_id,
        "is_ipc": device.is_ipc,
        "buttons": sorted(device.buttons),
        "switches": device.switches,
        "sensors": device.sensors,
        "selects": device.selects,
        "binary_sensors": device.binary_sensors,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ImouConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "unique_id": entry.unique_id,
                "data": dict(entry.data),
            },
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
            },
            "devices": [
                _serialize_device(device)
                for device in sorted(coordinator.devices, key=imou_device_identifier)
            ],
        },
        TO_REDACT,
    )
