"""Coordinator for handling data fetching and updates."""

import logging

from madvr.madvr import Madvr

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import MadVRConfigEntry
from .utils import cancel_tasks

_LOGGER = logging.getLogger(__name__)


class MadVRCoordinator(DataUpdateCoordinator[dict]):
    """My custom coordinator for push-based API."""

    config_entry: MadVRConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MadVRConfigEntry,
        client: Madvr,
        name: str,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Madvr Coordinator",
        )
        self.entry_id = config_entry.entry_id
        self.client = client
        self.name = name
        self.client.set_update_callback(self.handle_push_data)
        _LOGGER.debug("MadVRCoordinator initialized")

    async def _async_update_data(self):
        """No-op method for initial setup."""
        return

    def handle_push_data(self, data: dict):
        """Handle new data pushed from the API."""
        _LOGGER.debug("Received push data: %s", data)
        self.async_set_updated_data(data)

    async def async_handle_unload(self):
        """Handle unload."""
        _LOGGER.debug("Coordinator unloading")
        await cancel_tasks(self.client)
        self.client.stop()
        _LOGGER.debug("Coordinator closing connection")
        await self.client.close_connection()
        _LOGGER.debug("Unloaded")
