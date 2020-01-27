"""Support for the Carson doors."""
import logging

from homeassistant.components.lock import LockDevice

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Create the lights for the Ring devices."""
    doors = hass.data[DOMAIN][config_entry.entry_id]["doors"]

    entities = []

    for device in doors:
        entities.append(CarsonLock(device))

    async_add_entities(entities)


class CarsonLock(LockDevice):
    """Representation of an Carson Door lock."""

    def __init__(self, carson_door):
        """Initialize the light."""
        self._carson_door = carson_door

    @property
    def unique_id(self):
        """Name of the device."""
        return self._carson_door.unique_entity_id

    @property
    def assumed_state(self):
        """State of device is assumed."""
        return True

    @property
    def name(self):
        """Name of the device."""
        return self._carson_door.name

    def open(self, **kwargs):
        """Open the door."""
        self._carson_door.open()

    def lock(self, **kwargs):
        """Lock the device."""
        raise NotImplementedError("Carson door can only be opened.")

    def unlock(self, **kwargs):
        """Unlock the device."""
        raise NotImplementedError("Carson door can only be opened.")
