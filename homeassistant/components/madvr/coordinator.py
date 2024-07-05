"""Coordinator for handling data fetching and updates."""

import logging
from typing import Any

from madvr.madvr import Madvr

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type MadVRConfigEntry = ConfigEntry[MadVRCoordinator]


class MadVRCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Madvr coordinator for Envy (push-based API)."""

    config_entry: MadVRConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: Madvr,
    ) -> None:
        """Initialize madvr coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.entry_id = self.config_entry.entry_id
        # get the mac address from the config entry
        self.mac = self.config_entry.data.get(CONF_MAC)
        self.client = client
        self.client.set_update_callback(self.handle_push_data)
        _LOGGER.debug("MadVRCoordinator initialized with mac: %s", self.mac)

    def handle_push_data(self, data: dict[str, Any]) -> None:
        """Handle new data pushed from the API."""
        _LOGGER.debug("Received push data: %s", data)
        # inform HA that we have new data
        self.async_set_updated_data(data)

    async def handle_coordinator_load(self) -> None:
        """Handle operations on integration load."""
        _LOGGER.debug("Using loop: %s", self.client.loop)
        # tell the library to start background tasks
        await self.client.async_add_tasks()
        _LOGGER.debug("Added %s tasks to client", len(self.client.tasks))
