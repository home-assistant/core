"""
Support for locks through the SmartThings cloud API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/smartthings.lock/
"""
from homeassistant.components.lock import LockDevice
from homeassistant.const import (STATE_LOCKED, STATE_UNLOCKED)

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

DEPENDENCIES = ['smartthings']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add locks for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [SmartThingsLock(device) for device in broker.devices.values()
         if is_lock(device)])


def is_lock(device):
    """Determine if the device supports the lock capability."""
    from pysmartthings import Capability
    # Must be able to be turned on/off.
    if Capability.lock in device.capabilities:
        return True
    return False


class SmartThingsLock(SmartThingsEntity, LockDevice):
    """Define a SmartThings lock."""

    async def async_lock(self, **kwargs):
        """Lock the device."""
        await self._device.lock()
        self.async_schedule_update_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        await self._device.unlock()
        self.async_schedule_update_ha_state()

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._device.status.lock == STATE_LOCKED
