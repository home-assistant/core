"""Support for BTHome sensors."""
from __future__ import annotations

from bthome_ble import SensorDeviceClass as BTHomeSensorDeviceClass, SensorUpdate, Units

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .const import DOMAIN
from .coordinator import (
    BTHomePassiveBluetoothDataProcessor,
    BTHomePassiveBluetoothProcessorCoordinator,
)
from .device import device_key_to_bluetooth_entity_key

SENSOR_DESCRIPTIONS = {
    # Acceleration (m/s²)
    (
        BTHomeSensorDeviceClass.ACCELERATION,
        Units.ACCELERATION_METERS_PER_SQUARE_SECOND,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.ACCELERATION}_{Units.ACCELERATION_METERS_PER_SQUARE_SECOND}",
        native_unit_of_measurement=Units.ACCELERATION_METERS_PER_SQUARE_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Battery (percent)
    (BTHomeSensorDeviceClass.BATTERY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.BATTERY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Count (-)
    (BTHomeSensorDeviceClass.COUNT, None): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.COUNT}",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # CO2 (parts per million)
    (
        BTHomeSensorDeviceClass.CO2,
        Units.CONCENTRATION_PARTS_PER_MILLION,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.CO2}_{Units.CONCENTRATION_PARTS_PER_MILLION}",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Current (Ampere)
    (
        BTHomeSensorDeviceClass.CURRENT,
        Units.ELECTRIC_CURRENT_AMPERE,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.CURRENT}_{Units.ELECTRIC_CURRENT_AMPERE}",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Dew Point (°C)
    (BTHomeSensorDeviceClass.DEW_POINT, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.DEW_POINT}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Distance (mm)
    (
        BTHomeSensorDeviceClass.DISTANCE,
        Units.LENGTH_MILLIMETERS,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.DISTANCE}_{Units.LENGTH_MILLIMETERS}",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Distance (m)
    (BTHomeSensorDeviceClass.DISTANCE, Units.LENGTH_METERS): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.DISTANCE}_{Units.LENGTH_METERS}",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Duration (seconds)
    (BTHomeSensorDeviceClass.DURATION, Units.TIME_SECONDS): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.DURATION}_{Units.TIME_SECONDS}",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Energy (kWh)
    (
        BTHomeSensorDeviceClass.ENERGY,
        Units.ENERGY_KILO_WATT_HOUR,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.ENERGY}_{Units.ENERGY_KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    ),
    # Gas (m3)
    (
        BTHomeSensorDeviceClass.GAS,
        Units.VOLUME_CUBIC_METERS,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.GAS}_{Units.VOLUME_CUBIC_METERS}",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
    ),
    # Gyroscope (°/s)
    (
        BTHomeSensorDeviceClass.GYROSCOPE,
        Units.GYROSCOPE_DEGREES_PER_SECOND,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.GYROSCOPE}_{Units.GYROSCOPE_DEGREES_PER_SECOND}",
        native_unit_of_measurement=Units.GYROSCOPE_DEGREES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Humidity in (percent)
    (BTHomeSensorDeviceClass.HUMIDITY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.HUMIDITY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Illuminance (lux)
    (BTHomeSensorDeviceClass.ILLUMINANCE, Units.LIGHT_LUX): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.ILLUMINANCE}_{Units.LIGHT_LUX}",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Mass sensor (kg)
    (BTHomeSensorDeviceClass.MASS, Units.MASS_KILOGRAMS): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.MASS}_{Units.MASS_KILOGRAMS}",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Mass sensor (lb)
    (BTHomeSensorDeviceClass.MASS, Units.MASS_POUNDS): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.MASS}_{Units.MASS_POUNDS}",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.POUNDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Moisture (percent)
    (BTHomeSensorDeviceClass.MOISTURE, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.MOISTURE}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Packet Id (-)
    (BTHomeSensorDeviceClass.PACKET_ID, None): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.PACKET_ID}",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # PM10 (µg/m3)
    (
        BTHomeSensorDeviceClass.PM10,
        Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.PM10}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # PM2.5 (µg/m3)
    (
        BTHomeSensorDeviceClass.PM25,
        Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.PM25}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Power (Watt)
    (BTHomeSensorDeviceClass.POWER, Units.POWER_WATT): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.POWER}_{Units.POWER_WATT}",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Pressure (mbar)
    (BTHomeSensorDeviceClass.PRESSURE, Units.PRESSURE_MBAR): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.PRESSURE}_{Units.PRESSURE_MBAR}",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Rotation (°)
    (BTHomeSensorDeviceClass.ROTATION, Units.DEGREE): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.ROTATION}_{Units.DEGREE}",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Signal Strength (RSSI) (dB)
    (
        BTHomeSensorDeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # Speed (m/s)
    (
        BTHomeSensorDeviceClass.SPEED,
        Units.SPEED_METERS_PER_SECOND,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.SPEED}_{Units.SPEED_METERS_PER_SECOND}",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Temperature (°C)
    (BTHomeSensorDeviceClass.TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Timestamp (datetime object)
    (
        BTHomeSensorDeviceClass.TIMESTAMP,
        None,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.TIMESTAMP}",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # UV index (-)
    (
        BTHomeSensorDeviceClass.UV_INDEX,
        None,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.UV_INDEX}",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Volatile organic Compounds (VOC) (µg/m3)
    (
        BTHomeSensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS}_{Units.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER}",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Voltage (volt)
    (
        BTHomeSensorDeviceClass.VOLTAGE,
        Units.ELECTRIC_POTENTIAL_VOLT,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.VOLTAGE}_{Units.ELECTRIC_POTENTIAL_VOLT}",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Volume (L)
    (
        BTHomeSensorDeviceClass.VOLUME,
        Units.VOLUME_LITERS,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.VOLUME}_{Units.VOLUME_LITERS}",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Volume (mL)
    (
        BTHomeSensorDeviceClass.VOLUME,
        Units.VOLUME_MILLILITERS,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.VOLUME}_{Units.VOLUME_MILLILITERS}",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Volume Flow Rate (m3/hour)
    (
        BTHomeSensorDeviceClass.VOLUME_FLOW_RATE,
        Units.VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.VOLUME_FLOW_RATE}_{Units.VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR}",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Water (L)
    (
        BTHomeSensorDeviceClass.WATER,
        Units.VOLUME_LITERS,
    ): SensorEntityDescription(
        key=f"{BTHomeSensorDeviceClass.WATER}_{Units.VOLUME_LITERS}",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.TOTAL,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
                (description.device_class, description.native_unit_of_measurement)
            ]
            for device_key, description in sensor_update.entity_descriptions.items()
            if description.device_class
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BTHome BLE sensors."""
    coordinator: BTHomePassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = BTHomePassiveBluetoothDataProcessor(
        sensor_update_to_bluetooth_data_update
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            BTHomeBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class BTHomeBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[BTHomePassiveBluetoothDataProcessor],
    SensorEntity,
):
    """Representation of a BTHome BLE sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.processor.coordinator.sleepy_device or super().available
