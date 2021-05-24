"""Base class for KNX devices."""
from __future__ import annotations

from typing import cast

from xknx.devices import Climate as XknxClimate, Device as XknxDevice

from homeassistant.helpers.entity import Entity

from . import KNXModule
from .const import DOMAIN


class KnxEntity(Entity):
    """Representation of a KNX entity."""

    def __init__(self, device: XknxDevice) -> None:
        """Set up device."""
        self._device = device
        self._unique_id: str | None = None

    @property
    def name(self) -> str:
        """Return the name of the KNX device."""
        return self._device.name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        knx_module = cast(KNXModule, self.hass.data[DOMAIN])
        return knx_module.connected

    @property
    def should_poll(self) -> bool:
        """No polling needed within KNX."""
        return False

    @property
    def unique_id(self) -> str | None:
        """Return the unique id of the device."""
        return self._unique_id

    async def async_update(self) -> None:
        """Request a state update from KNX bus."""
        await self._device.sync()

    async def after_update_callback(self, device: XknxDevice) -> None:
        """Call after device was updated."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Store register state change callback."""
        self._device.register_device_updated_cb(self.after_update_callback)

        if isinstance(self._device, XknxClimate) and self._device.mode is not None:
            self._device.mode.register_device_updated_cb(self.after_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self._device.unregister_device_updated_cb(self.after_update_callback)

        if isinstance(self._device, XknxClimate) and self._device.mode is not None:
            self._device.mode.unregister_device_updated_cb(self.after_update_callback)
