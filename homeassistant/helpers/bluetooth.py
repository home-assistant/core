"""Common functions related to Bluetooth device management."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
)
from homeassistant.components.sensor import SensorEntityDescription

from .sensor import sensor_description_to_key, sensor_device_info_to_hass_device_info

if TYPE_CHECKING:
    # `sensor_state_data` is a second-party library (i.e. maintained by Home Assistant
    # core members) which is not strictly required by Home Assistant.
    # Therefore, we import it as a type hint only.
    from sensor_state_data import (
        BinarySensorDeviceClass,
        DeviceKey,
        SensorDeviceClass,
        SensorUpdate,
        Units,
    )


def device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a sensor_state_data device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
    sensor_descriptions: dict[
        tuple[SensorDeviceClass | None, Units | None], SensorEntityDescription
    ],
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor_state_data sensor update to a HA Bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): sensor_descriptions[
                sensor_key
            ]
            for device_key, description in sensor_update.entity_descriptions.items()
            if (sensor_key := sensor_description_to_key(description))
            in sensor_descriptions
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


def binary_sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
    binary_sensor_descriptions: dict[BinarySensorDeviceClass, SensorEntityDescription],
) -> PassiveBluetoothDataUpdate:
    """Convert a binary sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            device_key_to_bluetooth_entity_key(device_key): binary_sensor_descriptions[
                description.device_class
            ]
            for device_key, description in sensor_update.binary_entity_descriptions.items()
            if description.device_class in binary_sensor_descriptions
        },
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
    )
