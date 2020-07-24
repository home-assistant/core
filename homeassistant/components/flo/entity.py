"""Base entity class for Flo entities."""

from typing import Any, Dict

from homeassistant.helpers.entity import Entity

from .const import DOMAIN as FLO_DOMAIN
from .device import FloDevice


class FloEntity(Entity):
    """A base class for Flo entities."""

    def __init__(self, unique_id: str, name: str, device: FloDevice, **kwargs):
        """Init Flo entity."""
        self._unique_id: str = unique_id
        self._name: str = name
        self._device: FloDevice = device
        self._state: Any = None

    @property
    def name(self) -> str:
        """Return Entity's default name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return a device description for device registry."""
        return {
            "identifiers": {(FLO_DOMAIN, self._device.id)},
            "manufacturer": self._device.manufacturer,
            "model": self._device.model,
            "name": self._device.name,
            "sw_version": self._device.firmware_version,
        }

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self._device.available

    @property
    def force_update(self) -> bool:
        """Force update this entity."""
        return False

    @property
    def should_poll(self) -> bool:
        """Poll state from device."""
        return True

    async def async_update(self) -> None:
        """Retrieve the latest daily usage."""
