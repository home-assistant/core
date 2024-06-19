"""The yalexs_ble integration entities."""

from __future__ import annotations

from yalexs_ble import ConnectionInfo, LockInfo, LockState

from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .models import YaleXSBLEData


class YALEXSBLEEntity(Entity):
    """Base class for yale xs ble entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the entity."""
        self._data = data
        self._device = device = data.lock
        self._attr_available = False
        lock_state = device.lock_state
        lock_info = device.lock_info
        connection_info = device.connection_info
        assert lock_state is not None
        assert connection_info is not None
        assert lock_info is not None
        self._attr_unique_id = device.address
        self._attr_device_info = DeviceInfo(
            name=data.title,
            manufacturer=lock_info.manufacturer,
            model=lock_info.model,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
            identifiers={(DOMAIN, lock_info.serial)},
            sw_version=lock_info.firmware,
        )
        if device.lock_state:
            self._async_update_state(lock_state, lock_info, connection_info)

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_available = bool(not new_state.auth or new_state.auth.successful)

    @callback
    def _async_state_changed(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Handle state changed."""
        self._async_update_state(new_state, lock_info, connection_info)
        self.async_write_ha_state()

    @callback
    def _async_device_unavailable(
        self, _service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Handle device not longer being seen by the bluetooth stack."""
        self._attr_available = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            bluetooth.async_track_unavailable(
                self.hass, self._async_device_unavailable, self._device.address
            )
        )
        self.async_on_remove(self._device.register_callback(self._async_state_changed))
        return await super().async_added_to_hass()

    async def async_update(self) -> None:
        """Request a manual update."""
        await self._device.update()
