"""Support for Subaru door locks."""
import logging

from subarulink import InvalidPIN

from homeassistant.components.lock import LockEntity

from . import DOMAIN as SUBARU_DOMAIN, SubaruEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Subaru locks by config_entry."""
    controller = hass.data[SUBARU_DOMAIN][config_entry.entry_id]["controller"]
    coordinator = hass.data[SUBARU_DOMAIN][config_entry.entry_id]["coordinator"]
    vehicle_info = hass.data[SUBARU_DOMAIN][config_entry.entry_id]["vehicles"]
    entities = []
    for vin in vehicle_info.keys():
        if vehicle_info[vin]["has_remote"]:
            entities.append(SubaruLock(vehicle_info[vin], coordinator, controller))
    async_add_entities(entities, True)


class SubaruLock(SubaruEntity, LockEntity):
    """
    Representation of a Subaru door lock.

    Note that the Subaru API currently does not support returning the status of the locks. Therefore lock status is always unknown.
    """

    def __init__(self, vehicle_info, coordinator, controller):
        """Initialize the locks for the vehicle."""
        super().__init__(vehicle_info, coordinator)
        self.title = "Door Lock"
        self.hass_type = "lock"
        self.controller = controller

    async def async_lock(self, **kwargs):
        """Send the lock command."""
        _LOGGER.debug("Locking doors for: %s", self.vin)
        try:
            await self.controller.lock(self.vin)
        except InvalidPIN:
            _LOGGER.error("Invalid PIN")

    async def async_unlock(self, **kwargs):
        """Send the unlock command."""
        _LOGGER.debug("Unlocking doors for: %s", self.vin)
        try:
            await self.controller.unlock(self.vin)
        except InvalidPIN:
            _LOGGER.error("Invalid PIN")
