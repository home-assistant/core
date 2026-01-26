"""Support for Sensirion sensors."""

from __future__ import annotations

import dataclasses
import logging

from sensor_state_data import (
    DeviceKey,
    SensorDescription,
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
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: dict[
    tuple[SSDSensorDeviceClass, Units | None], SensorEntityDescription
] = {
    (
        SSDSensorDeviceClass.CO2,
        Units.CONCENTRATION_PARTS_PER_MILLION,
    ): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.CO2}_{Units.CONCENTRATION_PARTS_PER_MILLION}",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (SSDSensorDeviceClass.HUMIDITY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.HUMIDITY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (SSDSensorDeviceClass.TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def _to_sensor_key(
    description: SensorDescription,
) -> tuple[SSDSensorDeviceClass, Units | None]:
    assert description.device_class is not None
    return (description.device_class, description.native_unit_of_measurement)


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""

    def enable_entity_by_default(device_key: DeviceKey) -> bool:
        """Return true if the entity should be enabled by default, false otherwise.

        The purpose of this function is to assist with reducing the resources spent on collecting junk data from
        entities known to report inaccurate values.

        Background:
        The main purpose of the Sensirion MyCO2 gadget is to report CO₂ values, and it does so precisely. However,
        the additionally reported values (humidity, temperature) are not accurate. For example, in a real world setup
        with five pairs of each one MyCO2 gadget and a much more precise SHT43 DemoBoard, the reported humidity is off
        by 5-8 %, and the temperature by 1.3-2.8 °C. Those inaccuracies roughly match the performance stated in the
        data sheet of the SCD4x.
        As the official Sensirion Android app displays neither temperature nor humidity reported by the MyCO2 gadget, we
        should not, per default, enable those entities either.
        """

        # Bail out early if an unexpected sensor update gets passed.
        if (count := len(sensor_update.devices)) != 1:
            _LOGGER.warning(
                "Expecting exactly one device in a sensor update, but got %s", count
            )
            return True

        # Extract the first (and only) device info.
        (device_info,) = sensor_update.devices.values()

        # Values reported by devices other than the MyCO2 gadget are always enabled.
        if device_info.model != "Sensirion MyCO2":
            return True

        # Temperature and humidity values are inaccurate and should be disabled by default.
        if device_key.key in (
            SensorDeviceClass.HUMIDITY,
            SensorDeviceClass.TEMPERATURE,
        ):
            return False

        # At this point, only the CO₂ entity of the Sensirion MyCO2 gadget should be left.
        return True

    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): dataclasses.replace(
                SENSOR_DESCRIPTIONS[_to_sensor_key(description)],
                entity_registry_enabled_default=enable_entity_by_default(device_key),
            )
            for device_key, description in sensor_update.entity_descriptions.items()
            if _to_sensor_key(description) in SENSOR_DESCRIPTIONS
        },
        entity_data={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sensirion BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            SensirionBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class SensirionBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[float | int | None, SensorUpdate]
    ],
    SensorEntity,
):
    """Representation of a Sensirion BLE sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
