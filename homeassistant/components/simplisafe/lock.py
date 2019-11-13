"""Support for SimpliSafe locks."""
import logging

from simplipy.lock import LockStates

from homeassistant.components.lock import LockDevice
from homeassistant.const import STATE_LOCKED, STATE_UNKNOWN, STATE_UNLOCKED

from . import SimpliSafeEntity
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_LOCK_LOW_BATTERY = "lock_low_battery"
ATTR_JAMMED = "jammed"
ATTR_PIN_PAD_LOW_BATTERY = "pin_pad_low_battery"

STATE_MAP = {
    LockStates.locked: STATE_LOCKED,
    LockStates.unknown: STATE_UNKNOWN,
    LockStates.unlocked: STATE_UNLOCKED,
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SimpliSafe locks based on a config entry."""
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities(
        [
            SimpliSafeLock(system, lock)
            for system in simplisafe.systems.values()
            for lock in system.locks.values()
        ]
    )


class SimpliSafeLock(SimpliSafeEntity, LockDevice):
    """Define a SimpliSafe lock."""

    def __init__(self, system, lock):
        """Initialize."""
        super().__init__(system, lock.name, serial=lock.serial)
        self._lock = lock

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        return STATE_MAP.get(self._lock.state) == STATE_LOCKED

    async def async_lock(self, **kwargs):
        """Lock the lock."""
        await self._lock.lock()

    async def async_unlock(self, **kwargs):
        """Unlock the lock."""
        await self._lock.unlock()

    async def async_update(self):
        """Update lock status."""
        if self._lock.offline or self._lock.disabled:
            self._online = False
            return

        self._online = True

        self._attrs.update(
            {
                ATTR_LOCK_LOW_BATTERY: self._lock.lock_low_battery,
                ATTR_JAMMED: self._lock.state == LockStates.jammed,
                ATTR_PIN_PAD_LOW_BATTERY: self._lock.pin_pad_low_battery,
            }
        )
