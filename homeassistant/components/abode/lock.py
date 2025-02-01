"""Support for the Abode Security System locks."""

from typing import Any

from jaraco.abode.devices.lock import Lock

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AbodeSystem
from .const import DOMAIN
from .entity import AbodeDevice


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Abode lock devices."""
    data: AbodeSystem = hass.data[DOMAIN]

    async_add_entities(
        AbodeLock(data, device)
        for device in data.abode.get_devices(generic_type="lock")
    )


class AbodeLock(AbodeDevice, LockEntity):
    """Representation of an Abode lock."""

    _device: Lock
    _attr_name = None

    def lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self._device.lock()

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self._device.unlock()

    @property
    def is_locked(self) -> bool:
        """Return true if device is on."""
        return bool(self._device.is_locked)
