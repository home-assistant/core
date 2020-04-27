"""Support for Volvo On Call locks."""
import logging

from homeassistant.components.lock import LockEntity

from . import DATA_KEY, VolvoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Volvo On Call lock."""
    if discovery_info is None:
        return

    async_add_entities([VolvoLock(hass.data[DATA_KEY], *discovery_info)])


class VolvoLock(VolvoEntity, LockEntity):
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
