"""Support for Fluss Devices."""

import logging

from fluss_api.main import FlussApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import FlussButton

LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Fluss Devices."""

    entry_data = entry.runtime_data
    api: FlussApiClient = entry_data["api"]

    devices_data = await api.async_get_devices()
    devices = devices_data["devices"]

    device_info_list = []
    for device in devices:
        device_info = {
            "deviceId": device.get("deviceId"),
            "deviceName": device.get("deviceName"),
            "userType": device.get("userPermissions", {}).get("userType"),
        }
        device_info_list.append(device_info)

    buttons = [
        FlussButton(api, device) for device in devices if isinstance(device, dict)
    ]
    async_add_entities(buttons)
