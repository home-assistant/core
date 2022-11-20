"""Support for RuuviTag sensors."""
from __future__ import annotations

from functools import partial
from typing import Optional, Union

from sensor_state_data import SensorDeviceClass as SSDSensorDeviceClass, Units

from homeassistant import config_entries, const
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.bluetooth import sensor_update_to_bluetooth_data_update
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

SENSOR_DESCRIPTIONS = {
    (SSDSensorDeviceClass.TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=const.TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (SSDSensorDeviceClass.HUMIDITY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.HUMIDITY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=const.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (SSDSensorDeviceClass.PRESSURE, Units.PRESSURE_HPA): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.PRESSURE}_{Units.PRESSURE_HPA}",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=const.PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        SSDSensorDeviceClass.VOLTAGE,
        Units.ELECTRIC_POTENTIAL_MILLIVOLT,
    ): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.VOLTAGE}_{Units.ELECTRIC_POTENTIAL_MILLIVOLT}",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=const.ELECTRIC_POTENTIAL_MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        SSDSensorDeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=const.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    (SSDSensorDeviceClass.COUNT, None): SensorEntityDescription(
        key="movement_counter",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ruuvitag BLE sensors."""
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
            RuuvitagBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class RuuvitagBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[Optional[Union[float, int]]]
    ],
    SensorEntity,
):
    """Representation of a Ruuvitag BLE sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
