"""Support for moat ble sensors."""
from __future__ import annotations

from moat_ble import DeviceKey, SensorDeviceInfo, SensorUpdate

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
)
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_NAME
from homeassistant.helpers.entity import DeviceInfo

from .sensor import SENSOR_DESCRIPTIONS

ALL_PLATFORM_DESCRIPTIONS = SENSOR_DESCRIPTIONS


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def _sensor_device_info_to_hass(
    sensor_device_info: SensorDeviceInfo,
) -> DeviceInfo:
    """Convert a sensor device info to a sensor device info."""
    hass_device_info = DeviceInfo({})
    if sensor_device_info.name is not None:
        hass_device_info[ATTR_NAME] = sensor_device_info.name
    if sensor_device_info.manufacturer is not None:
        hass_device_info[ATTR_MANUFACTURER] = sensor_device_info.manufacturer
    if sensor_device_info.model is not None:
        hass_device_info[ATTR_MODEL] = sensor_device_info.model
    return hass_device_info


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: _sensor_device_info_to_hass(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): ALL_PLATFORM_DESCRIPTIONS[
                (description.device_class, description.native_unit_of_measurement)
            ]
            for device_key, description in sensor_update.entity_descriptions.items()
            if description.device_class and description.native_unit_of_measurement
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
