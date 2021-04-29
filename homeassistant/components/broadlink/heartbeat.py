"""Heartbeats for Broadlink devices."""
import datetime as dt
import logging

import broadlink as blk

from homeassistant.const import CONF_HOST
from homeassistant.helpers import event

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BroadlinkHeartbeat:
    """Manages heartbeats in the Broadlink integration.

    Some devices reboot when they cannot reach the cloud. This mechanism
    feeds their watchdog timers so they can be used offline.
    """

    INTERVAL = dt.timedelta(minutes=2)

    def __init__(self, hass):
        """Initialize the heartbeat."""
        self._hass = hass
        self._unsubscribe = None

    async def async_setup(self):
        """Set up the heartbeat."""
        if self._unsubscribe is None:
            await self.async_heartbeat(dt.datetime.now())
            self._unsubscribe = event.async_track_time_interval(
                self._hass, self.async_heartbeat, self.INTERVAL
            )

    async def async_unload(self):
        """Unload the heartbeat."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    async def async_heartbeat(self, now):
        """Send packets to feed watchdog timers."""
        hass = self._hass
        config_entries = hass.config_entries.async_entries(DOMAIN)

        for entry in config_entries:
            host = entry.data[CONF_HOST]
            try:
                await hass.async_add_executor_job(blk.ping, host)
            except OSError as err:
                _LOGGER.debug("Failed to send heartbeat to %s: %s", host, err)
            else:
                _LOGGER.debug("Heartbeat sent to %s", host)
