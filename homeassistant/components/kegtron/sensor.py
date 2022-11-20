"""Support for Kegtron sensors."""
from __future__ import annotations

from functools import partial
from typing import Optional, Union

from kegtron_ble import SensorDeviceClass as KegtronSensorDeviceClass, Units

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, VOLUME_LITERS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.bluetooth import sensor_update_to_bluetooth_data_update
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SENSOR_DESCRIPTIONS = {
    (KegtronSensorDeviceClass.PORT_COUNT, None): SensorEntityDescription(
        key=KegtronSensorDeviceClass.PORT_COUNT,
        icon="mdi:water-pump",
    ),
    (KegtronSensorDeviceClass.KEG_SIZE, Units.VOLUME_LITERS): SensorEntityDescription(
        key=KegtronSensorDeviceClass.KEG_SIZE,
        icon="mdi:keg",
        native_unit_of_measurement=VOLUME_LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (KegtronSensorDeviceClass.KEG_TYPE, None): SensorEntityDescription(
        key=KegtronSensorDeviceClass.KEG_TYPE,
        icon="mdi:keg",
    ),
    (
        KegtronSensorDeviceClass.VOLUME_START,
        Units.VOLUME_LITERS,
    ): SensorEntityDescription(
        key=KegtronSensorDeviceClass.VOLUME_START,
        icon="mdi:keg",
        native_unit_of_measurement=VOLUME_LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        KegtronSensorDeviceClass.VOLUME_DISPENSED,
        Units.VOLUME_LITERS,
    ): SensorEntityDescription(
        key=KegtronSensorDeviceClass.VOLUME_DISPENSED,
        icon="mdi:keg",
        native_unit_of_measurement=VOLUME_LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL,
    ),
    (KegtronSensorDeviceClass.PORT_STATE, None): SensorEntityDescription(
        key=KegtronSensorDeviceClass.PORT_STATE,
        icon="mdi:water-pump",
    ),
    (KegtronSensorDeviceClass.PORT_NAME, None): SensorEntityDescription(
        key=KegtronSensorDeviceClass.PORT_NAME,
        icon="mdi:water-pump",
    ),
    (
        KegtronSensorDeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{KegtronSensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Kegtron BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(
        partial(
            sensor_update_to_bluetooth_data_update,
            sensor_descriptions=SENSOR_DESCRIPTIONS,
        )
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            KegtronBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class KegtronBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[Optional[Union[float, int]]]
    ],
    SensorEntity,
):
    """Representation of a Kegtron sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
