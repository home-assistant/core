"""Support for yalexs ble binary sensors."""

from __future__ import annotations

from yalexs_ble import ConnectionInfo, DoorStatus, LockInfo, LockState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import YALEXSBLEConfigEntry
from .entity import YALEXSBLEEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YALEXSBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YALE XS binary sensors."""
    data = entry.runtime_data
    lock = data.lock
    if lock.lock_info and lock.lock_info.door_sense:
        async_add_entities([YaleXSBLEDoorSensor(data)])


class YaleXSBLEDoorSensor(YALEXSBLEEntity, BinarySensorEntity):
    """Yale XS BLE binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_is_on = new_state.door == DoorStatus.OPENED
        super()._async_update_state(new_state, lock_info, connection_info)
