"""Support for SimpliSafe locks."""
import logging

from homeassistant.components.lock import LockDevice

from . import SimpliSafeEntity
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SimpliSafe locks based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities(
        [
            SimpliSafeLock(system, lock)
            for system in simplisafe.systems.values()
            for lock in system.lock.values()
        ]
    )


class SimpliSafeLock(SimpliSafeEntity, LockDevice):
    """Define a SimpliSafe lock."""

    def __init__(self, system, lock):
        """Initialize."""
        super().__init__(system, lock.name, serial=lock.serial)
        self._lock = lock

    async def async_update(self):
        """Update lock status."""
        self._attrs.update({})
