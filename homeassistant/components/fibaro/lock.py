"""Support for Fibaro locks."""
from __future__ import annotations

from homeassistant.components.lock import ENTITY_ID_FORMAT, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FIBARO_DEVICES, FibaroDevice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fibaro locks."""
    async_add_entities(
        [
            FibaroLock(device)
            for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES]["lock"]
        ],
        True,
    )


class FibaroLock(FibaroDevice, LockEntity):
    """Representation of a Fibaro Lock."""

    def __init__(self, fibaro_device):
        """Initialize the Fibaro device."""
        self._state = False
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    def lock(self, **kwargs):
        """Lock the device."""
        self.action("secure")
        self._state = True

    def unlock(self, **kwargs):
        """Unlock the device."""
        self.action("unsecure")
        self._state = False

    @property
    def is_locked(self):
        """Return true if device is locked."""
        return self._state

    def update(self):
        """Update device state."""
        self._state = self.current_binary_state
