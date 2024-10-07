"""Support for Fluss Devices."""

import logging

from fluss_api.main import FlussApiClient

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

LOGGER = logging.getLogger(__package__)
DEFAULT_NAME = "Fluss +"


class FlussButton(ButtonEntity):
    """Representation of a Fluss cover device."""

    def __init__(self, api: FlussApiClient, device: dict) -> None:
        """Initialize the cover."""
        self.api = api
        self.device = device
        self._name = device.get("deviceName", "unknown")
        self._attr_unique_id = f"fluss_{device.get('deviceName', 'unknown')}"

    @property
    def name(self) -> str:
        """Return name of the cover."""
        return self._name

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.api.async_trigger_device(self.device["deviceId"])


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
