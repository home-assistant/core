"""Support for yalexs ble sensors."""
from __future__ import annotations

from yalexs_ble import ConnectionInfo, LockInfo, LockState

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YALE XS sensors."""
    data: YaleXSBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([YaleXSBLEDoorSensor(data)])


class YaleXSBLEDoorSensor(YALEXSBLEEntity, SensorEntity):
    """Yale XS BLE sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_name = "Signal strength"
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_native_value = connection_info.rssi
        super()._async_update_state(new_state, lock_info, connection_info)
