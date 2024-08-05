"""Support for xiaomi ble sensors."""

from __future__ import annotations

from typing import cast

from xiaomi_ble import DeviceClass, SensorUpdate, Units
from xiaomi_ble.parser import ExtendedSensorDeviceClass

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
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfConductivity,
    UnitOfElectricPotential,
    UnitOfMass,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .coordinator import XiaomiPassiveBluetoothDataProcessor
from .device import device_key_to_bluetooth_entity_key
from .types import XiaomiBLEConfigEntry

SENSOR_DESCRIPTIONS = {
    (DeviceClass.BATTERY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{DeviceClass.BATTERY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    (DeviceClass.CONDUCTIVITY, Units.CONDUCTIVITY): SensorEntityDescription(
        key=str(Units.CONDUCTIVITY),
        device_class=None,
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        DeviceClass.FORMALDEHYDE,
        Units.CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    ): SensorEntityDescription(
        key=f"{DeviceClass.FORMALDEHYDE}_{Units.CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER}",
        native_unit_of_measurement=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.HUMIDITY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{DeviceClass.HUMIDITY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.ILLUMINANCE, Units.LIGHT_LUX): SensorEntityDescription(
        key=f"{DeviceClass.ILLUMINANCE}_{Units.LIGHT_LUX}",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Impedance sensor (ohm)
    (DeviceClass.IMPEDANCE, Units.OHM): SensorEntityDescription(
        key=f"{DeviceClass.IMPEDANCE}_{Units.OHM}",
        icon="mdi:omega",
        native_unit_of_measurement=Units.OHM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Mass sensor (kg)
    (DeviceClass.MASS, Units.MASS_KILOGRAMS): SensorEntityDescription(
        key=f"{DeviceClass.MASS}_{Units.MASS_KILOGRAMS}",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Mass non stabilized sensor (kg)
    (DeviceClass.MASS_NON_STABILIZED, Units.MASS_KILOGRAMS): SensorEntityDescription(
        key=f"{DeviceClass.MASS_NON_STABILIZED}_{Units.MASS_KILOGRAMS}",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    (DeviceClass.MOISTURE, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{DeviceClass.MOISTURE}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.PRESSURE, Units.PRESSURE_MBAR): SensorEntityDescription(
        key=f"{DeviceClass.PRESSURE}_{Units.PRESSURE_MBAR}",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        DeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{DeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    (DeviceClass.TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{DeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (DeviceClass.VOLTAGE, Units.ELECTRIC_POTENTIAL_VOLT): SensorEntityDescription(
        key=f"{DeviceClass.VOLTAGE}_{Units.ELECTRIC_POTENTIAL_VOLT}",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # E.g. consumable sensor on WX08ZM and M1S-T500
    (ExtendedSensorDeviceClass.CONSUMABLE, Units.PERCENTAGE): SensorEntityDescription(
        key=str(ExtendedSensorDeviceClass.CONSUMABLE),
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Score after brushing with a toothbrush
    (ExtendedSensorDeviceClass.SCORE, None): SensorEntityDescription(
        key=str(ExtendedSensorDeviceClass.SCORE),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Counting during brushing
    (ExtendedSensorDeviceClass.COUNTER, Units.TIME_SECONDS): SensorEntityDescription(
        key=str(ExtendedSensorDeviceClass.COUNTER),
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Key id for locks and fingerprint readers
    (ExtendedSensorDeviceClass.KEY_ID, None): SensorEntityDescription(
        key=str(ExtendedSensorDeviceClass.KEY_ID), icon="mdi:identifier"
    ),
    # Lock method for locks
    (ExtendedSensorDeviceClass.LOCK_METHOD, None): SensorEntityDescription(
        key=str(ExtendedSensorDeviceClass.LOCK_METHOD), icon="mdi:key-variant"
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate[float | None]:
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
            device_key_to_bluetooth_entity_key(device_key): cast(
                float | None, sensor_values.native_value
            )
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiBLEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Xiaomi BLE sensors."""
    coordinator = entry.runtime_data
    processor = XiaomiPassiveBluetoothDataProcessor(
        sensor_update_to_bluetooth_data_update
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            XiaomiBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, SensorEntityDescription)
    )


class XiaomiBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[XiaomiPassiveBluetoothDataProcessor[float | None]],
    SensorEntity,
):
    """Representation of a xiaomi ble sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.processor.coordinator.sleepy_device or super().available
