"""Support for yalexs ble binary sensors."""
from __future__ import annotations

from yalexs_ble import DoorStatus, LockInfo, LockState

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YALE XS binary sensors."""
    data: YaleXSBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([YaleXSBLEDoorSensor(data)])


class YaleXSBLEDoorSensor(YALEXSBLEEntity, BinarySensorEntity):
    """Yale XS BLE binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR
    _attr_has_entity_name = True
    _attr_name = "Door"

    @callback
    def _async_update_state(self, new_state: LockState, lock_info: LockInfo) -> None:
        """Update the state."""
        self._attr_is_on = new_state.door == DoorStatus.OPENED
        super()._async_update_state(new_state, lock_info)
