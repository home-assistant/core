"""Representation of a Haus-Bus Entity."""

from typing import Any

from homeassistant.core import callback

# from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .device import HausbusDevice


class HausbusEntity(Entity):
    """Common base for HausBus Entities."""

    _attr_has_entity_name = True

    def __init__(
        self, channel_type: str, instance_id: int, device: HausbusDevice
    ) -> None:
        """Set up channel."""
        self._type = channel_type.lower()
        self._instance_id = instance_id
        self._device = device
        self._attr_unique_id = (
            f"{self._device.device_id}-{self._type}{self._instance_id}"
        )
        self._attr_device_info = self._device.device_info
        self._attr_translation_key = self._type
        self._attr_name = f"{channel_type} {self._instance_id}"

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """State push update."""
        raise NotImplementedError
