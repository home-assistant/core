"""Support for Fibaro locks."""
from __future__ import annotations

from typing import Any

from fiblary3.client.v4.models import DeviceModel, SceneModel

from homeassistant.components.lock import ENTITY_ID_FORMAT, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
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
            for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES][
                Platform.LOCK
            ]
        ],
        True,
    )


class FibaroLock(FibaroDevice, LockEntity):
    """Representation of a Fibaro Lock."""

    def __init__(self, fibaro_device: DeviceModel | SceneModel) -> None:
        """Initialize the Fibaro device."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    def lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self.action("secure")
        self._attr_is_locked = True

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self.action("unsecure")
        self._attr_is_locked = False

    def update(self) -> None:
        """Update device state."""
        self._attr_is_locked = self.current_binary_state
