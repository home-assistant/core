"""Yeelock Lock."""

import logging

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import Yeelock, YeelockDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the Yeelock lock platform."""
    device: Yeelock = hass.data[DOMAIN][entry.unique_id]
    lock = YeelockLock(device, hass)
    device._lock = lock  # Pass the reference
    async_add_entities([lock])
    return True


class YeelockLock(YeelockDeviceEntity, LockEntity):
    """Locks the device."""

    _attr_name = "Lock"
    _attr_supported_features = LockEntityFeature.OPEN

    @property
    def code_format(self):
        """Returns code format."""
        return None

    @property
    def is_locking(self):
        """Return true if lock is locking."""
        return self._attr_state == "locking"

    @property
    def is_unlocking(self):
        """Return true if lock is unlocking."""
        return self._attr_state == "unlocking"

    @property
    def is_jammed(self):
        """Return true if lock is jammed."""
        return self._attr_state == "jammed"

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._attr_state == "locked"

    async def _update_lock_state(self, new_state):
        """Update the lock state."""
        _LOGGER.debug("Setting state to %s", new_state)
        self._attr_state = new_state
        self.async_write_ha_state()

    async def async_lock(self):
        """Asynchronously lock."""
        await self.device.locker("lock")

    async def async_unlock(self):
        """Asynchronously unlock."""
        await self.device.locker("unlock")

    async def async_open(self):
        """Open the door quickly."""
        await self.device.locker("unlock_quick")
