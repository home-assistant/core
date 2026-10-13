"""Support for Chef iQ sensors."""

from typing import override

from chefiq_ble import ChefIqSensor, SensorUpdate

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
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
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from . import ChefIqConfigEntry
from .device import device_key_to_bluetooth_entity_key

PARALLEL_UPDATES = 0


def _temperature_description(
    sensor: ChefIqSensor, *, enabled_default: bool = True
) -> SensorEntityDescription:
    """Build a standard Celsius temperature description for a Chef iQ sensor."""
    return SensorEntityDescription(
        key=sensor,
        translation_key=sensor,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=enabled_default,
    )


SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    ChefIqSensor.FOOD_TEMPERATURE: _temperature_description(
        ChefIqSensor.FOOD_TEMPERATURE
    ),
    ChefIqSensor.AMBIENT_TEMPERATURE: _temperature_description(
        ChefIqSensor.AMBIENT_TEMPERATURE
    ),
    ChefIqSensor.PROBE_TIP_1_TEMPERATURE: _temperature_description(
        ChefIqSensor.PROBE_TIP_1_TEMPERATURE, enabled_default=False
    ),
    ChefIqSensor.PROBE_TIP_2_TEMPERATURE: _temperature_description(
        ChefIqSensor.PROBE_TIP_2_TEMPERATURE, enabled_default=False
    ),
    ChefIqSensor.PROBE_TIP_3_TEMPERATURE: _temperature_description(
        ChefIqSensor.PROBE_TIP_3_TEMPERATURE, enabled_default=False
    ),
    ChefIqSensor.PROBE_TIP_4_TEMPERATURE: _temperature_description(
        ChefIqSensor.PROBE_TIP_4_TEMPERATURE, enabled_default=False
    ),
    ChefIqSensor.SOC_TEMPERATURE: SensorEntityDescription(
        key=ChefIqSensor.SOC_TEMPERATURE,
        translation_key=ChefIqSensor.SOC_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    ChefIqSensor.BATTERY_PERCENT: SensorEntityDescription(
        key=ChefIqSensor.BATTERY_PERCENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # signal_strength (RSSI) is emitted automatically by the BluetoothData base
    # class, so it must have a description here.
    ChefIqSensor.SIGNAL_STRENGTH: SensorEntityDescription(
        key=ChefIqSensor.SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
                device_key.key
            ]
            for device_key in sensor_update.entity_descriptions
            if device_key.key in SENSOR_DESCRIPTIONS
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
            if device_key.key in SENSOR_DESCRIPTIONS
        },
        entity_names={},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChefIqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Chef iQ BLE sensors."""
    coordinator = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            ChefIqBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, SensorEntityDescription)
    )


class ChefIqBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[float | int | None, SensorUpdate]
    ],
    SensorEntity,
):
    """Representation of a Chef iQ sensor."""

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available.

        The sensor is only created when the device is seen.

        Since these are sleepy devices which stop broadcasting
        when not in use, we can't rely on the last update time
        so once we have seen the device we always return True.
        """
        return True

    @property
    @override
    def assumed_state(self) -> bool:
        """Return True if the device is no longer broadcasting."""
        return not self.processor.available
