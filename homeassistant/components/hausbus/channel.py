"""Representation of a Haus-Bus channel."""

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .device import HausbusDevice


class HausbusChannel(Entity):
    """Common base for HausBus channels."""

    _attr_has_entity_name = True

    def __init__(
        self, channel_type: str, instance_id: int, device: HausbusDevice
    ) -> None:
        """Set up channel."""
        self._type = channel_type.lower()
        self._instance_id = instance_id
        self._device = device

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this channel."""
        return f"{self._device.device_id}-{self._type}{self._instance_id}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return a device description for device registry."""
        return self._device.device_info

    @property
    def translation_key(self) -> str | None:
        """Return the translation key to translate the entity's states."""
        return self._type

    @property
    def name(self) -> str | None:
        """Return the channel name."""
        return f"{super().name} {self._instance_id}"

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """State push update."""
        raise NotImplementedError
