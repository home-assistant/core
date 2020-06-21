"""Support for Tesla door locks."""
import logging

from homeassistant.components.lock import LockEntity
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED

from . import DOMAIN as TESLA_DOMAIN, TeslaDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Tesla binary_sensors by config_entry."""
    entities = [
        TeslaLock(
            device,
            hass.data[TESLA_DOMAIN][config_entry.entry_id]["controller"],
            config_entry,
        )
        for device in hass.data[TESLA_DOMAIN][config_entry.entry_id]["devices"]["lock"]
    ]
    async_add_entities(entities, True)


class TeslaLock(TeslaDevice, LockEntity):
    """Representation of a Tesla door lock."""

    def __init__(self, tesla_device, controller, config_entry):
        """Initialise of the lock."""
        self._state = None
        super().__init__(tesla_device, controller, config_entry)

    async def async_lock(self, **kwargs):
        """Send the lock command."""
        _LOGGER.debug("Locking doors for: %s", self._name)
        await self.tesla_device.lock()

    async def async_unlock(self, **kwargs):
        """Send the unlock command."""
        _LOGGER.debug("Unlocking doors for: %s", self._name)
        await self.tesla_device.unlock()

    @property
    def is_locked(self):
        """Get whether the lock is in locked state."""
        return self._state == STATE_LOCKED

    async def async_update(self):
        """Update state of the lock."""
        _LOGGER.debug("Updating state for: %s", self._name)
        await super().async_update()
        self._state = STATE_LOCKED if self.tesla_device.is_locked() else STATE_UNLOCKED
