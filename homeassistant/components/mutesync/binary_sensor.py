"""Mutesync binary sensor entities."""
import asyncio

import aiohttp
import async_timeout

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Mutesync button."""
    client = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([MuteStatus(client)], True)


class MuteStatus(BinarySensorEntity):
    """Class to hold Mutesync basic info."""

    def __init__(self, client):
        """Initialize binary sensor."""
        self.client = client
        self._is_on = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Mute Status"

    @property
    def available(self):
        """Return if state is available from sensor."""
        return self._is_on is not None

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._is_on

    async def async_update(self):
        """Update state."""
        try:
            async with async_timeout.timeout(10):
                status = await self.client.get_state()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            self._is_on = None
            return

        if not status["in_meeting"]:
            self._is_on = None
        else:
            self._is_on = status["muted"]
