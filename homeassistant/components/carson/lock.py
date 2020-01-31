"""Support for the Carson doors."""
import asyncio
import logging

from homeassistant.components.lock import SUPPORT_OPEN, LockDevice

from .const import DOMAIN, UNLOCKED_TIMESPAN_SEC
from .entity import CarsonEntityMixin

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Create the Locks for the Carson devices."""
    _LOGGER.debug("Setting up Carson LockDevice entries")
    carson = hass.data[DOMAIN][config_entry.entry_id]["api"]
    doors = [door for b in carson.buildings for door in b.doors]

    async_add_entities(CarsonLock(config_entry.entry_id, door) for door in doors)


class CarsonLock(CarsonEntityMixin, LockDevice):
    """Representation of an Carson Door lock."""

    def __init__(self, config_entry_id, carson_door):
        """Initialize the lock."""
        super().__init__(config_entry_id, carson_door)

        self._carson_door = carson_door
        self._is_locked = True

    @property
    def supported_features(self):
        """Carson locks support open."""
        return SUPPORT_OPEN

    @property
    def assumed_state(self):
        """State of device is assumed."""
        return True

    @property
    def name(self):
        """Name of the device."""
        return self._carson_door.name

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        return self._is_locked

    @staticmethod
    def unlocked_timespan():
        """Return default unlocked timestamp."""
        return UNLOCKED_TIMESPAN_SEC

    def open(self, **kwargs):
        """Open the door."""
        self._carson_door.open()
        self._is_locked = False
        self.schedule_update_ha_state()
        self.hass.add_job(self.async_set_locked_after_delay(self.unlocked_timespan()))

    def lock(self, **kwargs):
        """Lock the device."""
        raise NotImplementedError("Door can only be opened/unlocked.")

    def unlock(self, **kwargs):
        """Unlock the device."""
        self.open()

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "provider": self._carson_door.provider,
            "is_active": self._carson_door.is_active,
            "disabled": self._carson_door.disabled,
            "is_unit_door": self._carson_door.is_unit_door,
            "staff_only": self._carson_door.staff_only,
            "default_in_building": self._carson_door.default_in_building,
            "external_id": self._carson_door.external_id,
            "available": self._carson_door.available,
        }

    async def async_set_locked_after_delay(self, delay):
        """Delay x seconds and update state to LOCKED."""
        await asyncio.sleep(delay)
        self._is_locked = True
        self.schedule_update_ha_state()
