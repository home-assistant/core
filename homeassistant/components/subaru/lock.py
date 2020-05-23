"""Support for Subaru door locks."""
import logging

from subarulink.exceptions import InvalidPIN

from homeassistant.components.lock import LockEntity

from . import DOMAIN as SUBARU_DOMAIN, SubaruDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Subaru locks by config_entry."""
    controller = hass.data[SUBARU_DOMAIN][config_entry.entry_id]["controller"]
    entities = []
    for device in hass.data[SUBARU_DOMAIN][config_entry.entry_id]["devices"]["lock"]:
        entities.append(SubaruLock(device, controller, config_entry))
    async_add_entities(entities, True)


class SubaruLock(SubaruDevice, LockEntity):
    """
    Representation of a Subaru door lock.

    Note that the Subaru API currently does not support returning the status of the locks. Therefore lock status is always unknown.
    """

    async def async_lock(self, **kwargs):
        """Send the lock command."""
        _LOGGER.debug("Locking doors for: %s", self._name)
        try:
            await self.subaru_device.lock()
        except InvalidPIN:
            _LOGGER.error("Invalid PIN")

    async def async_unlock(self, **kwargs):
        """Send the unlock command."""
        _LOGGER.debug("Unlocking doors for: %s", self._name)
        try:
            await self.subaru_device.unlock()
        except InvalidPIN:
            _LOGGER.error("Invalid PIN")
