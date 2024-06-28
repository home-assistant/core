"""Device for Fluss Device."""

import logging

from homeassistant.components.button import ButtonEntity

from .api import FlussApiClient

LOGGER = logging.getLogger(__package__)
DEFAULT_NAME = "Fluss +"


class FlussButton(ButtonEntity):
    """Representation of a Fluss cover device."""

    def __init__(self, api: FlussApiClient, device: dict) -> None:
        """Initializr the cover."""
        self.api = api
        self.device = device
        self._name = device["deviceName"]
        self._attr_unique_id = f"fluss_{device['deviceId']}"

    @property
    def name(self) -> str:
        """Return name of the cover."""
        return self._name

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.api.async_trigger_device(self.device["deviceId"])
