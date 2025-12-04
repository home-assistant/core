"""Support for RuuviTag sensors."""

from __future__ import annotations

from sensor_state_data import (
    DeviceKey,
    SensorDeviceClass as SSDSensorDeviceClass,
    SensorUpdate,
    Units,
)

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .const import DOMAIN

SENSOR_DESCRIPTIONS = {
    "temperature": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.HUMIDITY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pressure": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.PRESSURE}_{Units.PRESSURE_HPA}",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "voltage": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.VOLTAGE}_{Units.ELECTRIC_POTENTIAL_MILLIVOLT}",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "signal_strength": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "movement_counter": SensorEntityDescription(
        key="movement_counter",
        translation_key="movement_counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    # Acceleration keys exported in newer versions of ruuvitag-ble
    "acceleration_x": SensorEntityDescription(
        key=f"acceleration_x_{Units.ACCELERATION_METERS_PER_SQUARE_SECOND}",
        translation_key="acceleration_x",
        native_unit_of_measurement=Units.ACCELERATION_METERS_PER_SQUARE_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "acceleration_y": SensorEntityDescription(
        key=f"acceleration_y_{Units.ACCELERATION_METERS_PER_SQUARE_SECOND}",
        translation_key="acceleration_y",
        native_unit_of_measurement=Units.ACCELERATION_METERS_PER_SQUARE_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "acceleration_z": SensorEntityDescription(
        key=f"acceleration_z_{Units.ACCELERATION_METERS_PER_SQUARE_SECOND}",
        translation_key="acceleration_z",
        native_unit_of_measurement=Units.ACCELERATION_METERS_PER_SQUARE_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    "acceleration_total": SensorEntityDescription(
        key=f"acceleration_total_{Units.ACCELERATION_METERS_PER_SQUARE_SECOND}",
        translation_key="acceleration_total",
        native_unit_of_measurement=Units.ACCELERATION_METERS_PER_SQUARE_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # Keys exported for dataformat 06/e1 sensors in newer versions of ruuvitag-ble
    "pm1": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.PM1}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pm4": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.PM4}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.PM4,
        native_unit_of_measurement=Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pm10": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.PM10}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "pm25": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.PM25}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "carbon_dioxide": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.CO2}_{Units.CONCENTRATION_PARTS_PER_MILLION}",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=Units.CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "illuminance": SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.ILLUMINANCE}_{Units.LIGHT_LUX}",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=Units.LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "voc_index": SensorEntityDescription(
        key="voc_index",
        translation_key="voc_index",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "nox_index": SensorEntityDescription(
        key="nox_index",
        translation_key="nox_index",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    entity_descriptions: dict[PassiveBluetoothEntityKey, EntityDescription] = {}
    entity_data = {}
    for device_key, sensor_values in sensor_update.entity_values.items():
        bek = _device_key_to_bluetooth_entity_key(device_key)
        entity_data[bek] = sensor_values.native_value
    for device_key in sensor_update.entity_descriptions:
        bek = _device_key_to_bluetooth_entity_key(device_key)
        if sk_description := SENSOR_DESCRIPTIONS.get(device_key.key):
            entity_descriptions[bek] = sk_description

    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions=entity_descriptions,
        entity_data=entity_data,
        entity_names={},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ruuvi BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            RuuvitagBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class RuuvitagBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[float | int | None, SensorUpdate]
    ],
    SensorEntity,
):
    """Representation of a Ruuvi BLE sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
