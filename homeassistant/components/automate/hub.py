"""Code to handle a Pulse Hub."""
from __future__ import annotations

import asyncio
import logging

import aiopulse2

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import AUTOMATE_ENTITY_REMOVE, AUTOMATE_HUB_UPDATE
from .helpers import update_devices

_LOGGER = logging.getLogger(__name__)


class PulseHub:
    """Manages a single Pulse Hub."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.api: aiopulse2.Hub | None = None
        self.tasks = []
        self.current_rollers = {}
        self.cleanup_callbacks = []

    @property
    def title(self):
        """Return the title of the hub shown in the integrations list."""
        return f"{self.api.name} ({self.api.host})"

    @property
    def host(self):
        """Return the host of this hub."""
        return self.config_entry.data["host"]

    async def async_setup(self):
        """Set up a hub based on host parameter."""
        host = self.host

        hub = aiopulse2.Hub(host, propagate_callbacks=True)

        self.api = hub

        hub.callback_subscribe(self.async_notify_update)
        self.tasks.append(asyncio.create_task(hub.run()))

        _LOGGER.debug("Hub setup complete")
        return True

    async def async_reset(self):
        """Reset this hub to default state."""
        for cleanup_callback in self.cleanup_callbacks:
            cleanup_callback()

        # If not setup
        if self.api is None:
            return False

        self.api.callback_unsubscribe(self.async_notify_update)
        await self.api.stop()
        del self.api
        self.api = None

        # Wait for any running tasks to complete
        await asyncio.wait(self.tasks)

        return True

    async def async_notify_update(self, hub=None):
        """Evaluate entities when hub reports that update has occurred."""
        _LOGGER.debug("Hub {self.title} updated")

        await update_devices(self.hass, self.config_entry, self.api.rollers)
        self.hass.config_entries.async_update_entry(self.config_entry, title=self.title)

        async_dispatcher_send(
            self.hass, AUTOMATE_HUB_UPDATE.format(self.config_entry.entry_id)
        )

        for unique_id in list(self.current_rollers):
            if unique_id not in self.api.rollers:
                _LOGGER.debug("Notifying remove of %s", unique_id)
                self.current_rollers.pop(unique_id)
                async_dispatcher_send(
                    self.hass, AUTOMATE_ENTITY_REMOVE.format(unique_id)
                )
