"""Support for Fibaro locks."""
from __future__ import annotations

from homeassistant.components.lock import DOMAIN, LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import FIBARO_DEVICES, FibaroDevice


# Ais dom
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fibaro locks."""
    async_add_entities(
        [FibaroLock(device) for device in hass.data[FIBARO_DEVICES]["lock"]], True
    )


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fibaro locks."""
    if discovery_info is None:
        return

    add_entities(
        [FibaroLock(device) for device in hass.data[FIBARO_DEVICES]["lock"]], True
    )


class FibaroLock(FibaroDevice, LockEntity):
    """Representation of a Fibaro Lock."""

    def __init__(self, fibaro_device):
        """Initialize the Fibaro device."""
        self._state = False
        super().__init__(fibaro_device)
        self.entity_id = f"{DOMAIN}.{self.ha_id}"

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
