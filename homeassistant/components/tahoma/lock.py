"""Support for TaHoma lock."""
import logging

from homeassistant.components.lock import DOMAIN as LOCK, LockEntity
from homeassistant.const import STATE_LOCKED

from .const import DOMAIN
from .tahoma_device import TahomaDevice

_LOGGER = logging.getLogger(__name__)

COMMAND_LOCK = "lock"
COMMAND_UNLOCK = "unlock"

CORE_LOCKED_UNLOCKED_STATE = "core:LockedUnlockedState"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TaHoma locks from a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        TahomaLock(device.deviceurl, coordinator)
        for device in data["entities"].get(LOCK)
    ]

    async_add_entities(entities)


class TahomaLock(TahomaDevice, LockEntity):
    """Representation of a TaHoma Lock."""

    async def async_unlock(self, **_):
        """Unlock method."""
        await self.async_execute_command(COMMAND_UNLOCK)

    async def async_lock(self, **_):
        """Lock method."""
        await self.async_execute_command(COMMAND_LOCK)

    @property
    def is_locked(self):
        """Return True if the lock is locked."""
        return self.select_state(CORE_LOCKED_UNLOCKED_STATE) == STATE_LOCKED
