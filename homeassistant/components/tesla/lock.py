"""Support for Tesla door locks."""
import logging

from homeassistant.components.lock import LockEntity

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Tesla binary_sensors by config_entry."""
    entities = [
        TeslaLock(
            device,
            hass.data[TESLA_DOMAIN][config_entry.entry_id]["coordinator"],
        )
        for device in hass.data[TESLA_DOMAIN][config_entry.entry_id]["devices"]["lock"]
    ]
    async_add_entities(entities, True)


class TeslaLock(TeslaDevice, LockEntity):
    """Representation of a Tesla door lock."""

    async def async_lock(self, **kwargs):
        """Send the lock command."""
        _LOGGER.debug("Locking doors for: %s", self.name)
        await self.tesla_device.lock()

    async def async_unlock(self, **kwargs):
        """Send the unlock command."""
        _LOGGER.debug("Unlocking doors for: %s", self.name)
        await self.tesla_device.unlock()

    @property
    def is_locked(self):
        """Get whether the lock is in locked state."""
        if self.tesla_device.is_locked() is None:
            return None
        return self.tesla_device.is_locked()
