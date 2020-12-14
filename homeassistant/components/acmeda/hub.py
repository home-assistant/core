"""Code to handle a Pulse Hub."""
import asyncio
from typing import Optional

import aiopulse

from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import ACMEDA_ENTITY_REMOVE, ACMEDA_HUB_UPDATE, LOGGER
from .helpers import update_devices


class PulseHub:
    """Manages a single Pulse Hub."""

    def __init__(self, hass, config_entry):
        """Initialize the system."""
        self.config_entry = config_entry
        self.hass = hass
        self.api: Optional[aiopulse.Hub] = None
        self.tasks = []
        self.current_rollers = {}
        self.cleanup_callbacks = []

    @property
    def title(self):
        """Return the title of the hub shown in the integrations list."""
        return f"{self.api.id} ({self.api.host})"

    @property
    def host(self):
        """Return the host of this hub."""
        return self.config_entry.data["host"]

    async def async_setup(self, tries=0):
        """Set up a hub based on host parameter."""
        host = self.host

        hub = aiopulse.Hub(host)
        self.api = hub

        hub.callback_subscribe(self.async_notify_update)
        self.tasks.append(asyncio.create_task(hub.run()))

        LOGGER.debug("Hub setup complete")
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

    async def async_notify_update(self, update_type):
        """Evaluate entities when hub reports that update has occurred."""
        LOGGER.debug("Hub {update_type.name} updated")

        if update_type == aiopulse.UpdateType.rollers:
            await update_devices(self.hass, self.config_entry, self.api.rollers)
            self.hass.config_entries.async_update_entry(
                self.config_entry, title=self.title
            )

            async_dispatcher_send(
                self.hass, ACMEDA_HUB_UPDATE.format(self.config_entry.entry_id)
            )

            for unique_id in list(self.current_rollers):
                if unique_id not in self.api.rollers:
                    LOGGER.debug("Notifying remove of %s", unique_id)
                    self.current_rollers.pop(unique_id)
                    async_dispatcher_send(
                        self.hass, ACMEDA_ENTITY_REMOVE.format(unique_id)
                    )
