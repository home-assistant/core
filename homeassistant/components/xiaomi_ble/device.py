"""Support for Xioami BLE devices."""
from __future__ import annotations

from xiaomi_ble import DeviceKey, SensorDeviceInfo

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothEntityKey,
)
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_NAME
from homeassistant.helpers.entity import DeviceInfo


def device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def sensor_device_info_to_hass(
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
