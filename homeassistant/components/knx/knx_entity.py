"""Base class for KNX devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xknx.devices import Device as XknxDevice

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

if TYPE_CHECKING:
    from . import KNXModule

SIGNAL_ENTITY_REMOVE = f"{DOMAIN}_entity_remove_signal.{{}}"


class KnxEntity(Entity):
    """Representation of a KNX entity."""

    _attr_should_poll = False

    def __init__(self, knx_module: KNXModule, device: XknxDevice) -> None:
        """Set up device."""
        self._knx_module = knx_module
        self._device = device

    @property
    def name(self) -> str:
        """Return the name of the KNX device."""
        return self._device.name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._knx_module.connected

    async def async_update(self) -> None:
        """Request a state update from KNX bus."""
        await self._device.sync()

    def after_update_callback(self, _device: XknxDevice) -> None:
        """Call after device was updated."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Store register state change callback and start device object."""
        self._device.register_device_updated_cb(self.after_update_callback)
        self._device.xknx.devices.async_add(self._device)
        # super call needed to have methods of mulit-inherited classes called
        # eg. for restoring state (like _KNXSwitch)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self._device.unregister_device_updated_cb(self.after_update_callback)
        self._device.xknx.devices.async_remove(self._device)


class KnxUIEntity(KnxEntity):
    """Representation of a KNX UI entity."""

    _attr_unique_id: str

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity added to hass."""
        await super().async_added_to_hass()
        self._knx_module.config_store.entities.add(self._attr_unique_id)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_ENTITY_REMOVE.format(self._attr_unique_id),
                self.async_remove,
            )
        )
