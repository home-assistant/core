"""mütesync binary sensor entities."""
import asyncio

import aiohttp
import async_timeout

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the mütesync button."""
    client = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([MuteStatus(client)], True)


class MuteStatus(BinarySensorEntity):
    """Class to hold mütesync basic info."""

    def __init__(self, client):
        """Initialize binary sensor."""
        self.client = client
        self._status = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Mute Status"

    @property
    def unique_id(self):
        """Return the unique ID of the sensor."""
        if self._status is None:
            return None
        return f"{self._status['user-id']}-mute"

    @property
    def available(self):
        """Return if state is available from sensor."""
        return self._status and self._status["in_meeting"]

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._is_on

    @property
    def device_info(self):
        """Return the device info of the sensor."""
        if self._status is None:
            return None

        return {
            "identifiers": {(DOMAIN, self._status["user-id"])},
            "name": "mutesync",
            "manufacturer": "mütesync",
            "model": "mutesync app",
            "entry_type": "service",
        }

    async def async_update(self):
        """Update state."""
        try:
            async with async_timeout.timeout(10):
                self._status = await self.client.get_state()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            self._status = None
