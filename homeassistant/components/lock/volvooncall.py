"""
Support for Volvo On Call locks.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lock.volvooncall/
"""
import logging

from homeassistant.components.lock import LockDevice
from homeassistant.components.volvooncall import VolvoEntity, DATA_KEY

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Volvo On Call lock."""
    if discovery_info is None:
        return

    async_add_entities([VolvoLock(hass.data[DATA_KEY], *discovery_info)])


class VolvoLock(VolvoEntity, LockDevice):
    """Represents a car lock."""

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self.instrument.is_locked

    async def async_lock(self, **kwargs):
        """Lock the car."""
        await self.instrument.lock()

    async def async_unlock(self, **kwargs):
        """Unlock the car."""
        await self.instrument.unlock()
