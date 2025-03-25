"""Support for Fluss Devices."""

import logging

from fluss_api.main import FlussApiClient

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

LOGGER = logging.getLogger(__package__)
DEFAULT_NAME = "Fluss +"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fluss Devices."""

    api = entry.runtime_data

    devices_data = await api.async_get_devices()
    devices = devices_data["devices"]

    async_add_entities(
        FlussButton(api, device) for device in devices if isinstance(device, dict)
    )


class FlussButton(ButtonEntity):
    """Representation of a Fluss cover device."""

    def __init__(self, api: FlussApiClient, device: dict) -> None:
        """Initialize the cover."""
        if "deviceId" not in device:
            raise ValueError("Device missing required 'deviceId' attribute.")

        self.api = api
        self.device = device
        self._name = device.get("deviceName", "Unknown Device")
        self._attr_unique_id = f"fluss_{device['deviceId']}"

    @property
    def name(self) -> str:
        """Return name of the cover."""
        return self._name

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.api.async_trigger_device(self.device["deviceId"])
