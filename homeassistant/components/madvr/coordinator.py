"""Coordinator for handling data fetching and updates."""

import asyncio
import logging

from madvr.madvr import Madvr

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .utils import cancel_tasks

_LOGGER = logging.getLogger(__name__)


class MadVRCoordinator(DataUpdateCoordinator[dict]):
    """My custom coordinator for push-based API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: Madvr,
        name: str,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Madvr Coordinator",
        )
        self.entry_id = self.config_entry.entry_id
        self.client = client
        self.name = name
        self.client.set_update_callback(self.handle_push_data)
        self.tasks: list[asyncio.Task] = []
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

    async def async_add_tasks(self):
        """Add background tasks."""
        # handle queue
        task_queue = self.hass.loop.create_task(self.handle_queue())
        self.tasks.append(task_queue)

        task_notif = self.hass.loop.create_task(self.client.read_notifications())
        self.tasks.append(task_notif)

        task_hb = self.hass.loop.create_task(self.client.send_heartbeat())
        self.tasks.append(task_hb)

    async def async_cancel_tasks(self):
        """Cancel all tasks."""
        for task in self.tasks:
            if not task.done():
                task.cancel()
