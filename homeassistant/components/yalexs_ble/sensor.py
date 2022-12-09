"""Support for yalexs ble sensors."""
from __future__ import annotations

from yalexs_ble import ConnectionInfo, LockInfo, LockState

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import YALEXSBLEEntity
from .models import YaleXSBLEData

SENSORS = (
    SensorEntityDescription(
        key="",  # No key for the original RSSI sensor unique id
        name="Signal strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="battery",
        name="Battery level",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        has_entity_name=True,
        native_unit_of_measurement=PERCENTAGE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YALE XS Bluetooth sensors."""
    data: YaleXSBLEData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(YaleXSBLESensor(description, data) for description in SENSORS)


class YaleXSBLESensor(YALEXSBLEEntity, SensorEntity):
    """Yale XS Bluetooth sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        data: YaleXSBLEData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data)
        self._attr_unique_id = f"{data.lock.address}{description.key}"

    @callback
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        if self.entity_description.key == "battery":
            battery = new_state.battery
            self._attr_native_value = battery.percentage if battery else None
        else:
            self._attr_native_value = connection_info.rssi
        super()._async_update_state(new_state, lock_info, connection_info)
