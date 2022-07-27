"""The yalexs_ble integration entities."""
from __future__ import annotations

from yalexs_ble import LockState

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .models import YaleXSBLEData


class YALEXSBLEEntity(Entity):
    """Base class for yale xs ble entities."""

    _attr_should_poll = False

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the entity."""
        self._data = data
        self._device = data.lock
        self._attr_available = False
        self._attr_unique_id = data.local_name
        self._attr_device_info = DeviceInfo(
            name=data.title,
            manufacturer="Yale",
            identifiers={(DOMAIN, data.local_name)},
        )
        if self._device.lock_state:
            self._async_update_state(self._device.lock_state)

    @callback
    def _async_update_state(self, new_state: LockState) -> None:
        """Update the state."""
        self._attr_available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(self._device.register_callback(self._async_update_state))
        return await super().async_added_to_hass()
