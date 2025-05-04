"""Coordinator for handling data fetching and updates."""

from __future__ import annotations

import logging
from typing import Any

from madvr.madvr import Madvr

from homeassistant.config_entries import ConfigEntry
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
        config_entry: MadVRConfigEntry,
        client: Madvr,
    ) -> None:
        """Initialize madvr coordinator."""
        super().__init__(hass, _LOGGER, config_entry=config_entry, name=DOMAIN)
        assert self.config_entry.unique_id
        self.mac = self.config_entry.unique_id
        self.client = client
        # this does not use poll/refresh, so we need to set this to not None on init
        self.data = {}
        # this passes a callback to the client to push new data to the coordinator
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
