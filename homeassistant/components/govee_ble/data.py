"""The Govee Bluetooth integration."""
from __future__ import annotations

from bluetooth_sensor_state_data import SensorUpdate
from sensor_state_data import DeviceClass, DeviceKey

from homeassistant.components.bluetooth.update_coordinator import (
    BluetoothDataUpdate,
    BluetoothEntityKey,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import ATTR_MODEL, ATTR_NAME
from homeassistant.helpers.entity import DeviceInfo

SENSOR_DEVICE_CLASS_TO_HASS = {
    DeviceClass.APPARENT_POWER: SensorDeviceClass.APPARENT_POWER,
    DeviceClass.HUMIDITY: SensorDeviceClass.HUMIDITY,
    DeviceClass.ILLUMINANCE: SensorDeviceClass.ILLUMINANCE,
    DeviceClass.TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    DeviceClass.PRESSURE: SensorDeviceClass.PRESSURE,
    DeviceClass.VOLTAGE: SensorDeviceClass.VOLTAGE,
    DeviceClass.CURRENT: SensorDeviceClass.CURRENT,
    DeviceClass.FREQUENCY: SensorDeviceClass.FREQUENCY,
    DeviceClass.POWER: SensorDeviceClass.POWER,
    DeviceClass.ENERGY: SensorDeviceClass.ENERGY,
    DeviceClass.POWER_FACTOR: SensorDeviceClass.POWER_FACTOR,
    DeviceClass.SIGNAL_STRENGTH: SensorDeviceClass.SIGNAL_STRENGTH,
}

RSSI_KEY = "rssi"


def _device_key_to_bluetooth_entity_key(device_key: DeviceKey) -> BluetoothEntityKey:
    """Convert a device key to an entity key."""
    return BluetoothEntityKey(device_key.key, device_key.device_id)


def _sensor_device_class_to_hass(
    sensor_device_class: DeviceClass | None,
) -> SensorDeviceClass | None:
    """Convert a sensor device class to a sensor device class."""
    if sensor_device_class is None:
        return None
    return SENSOR_DEVICE_CLASS_TO_HASS.get(sensor_device_class)


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> BluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return BluetoothDataUpdate(
        devices={
            device_id: DeviceInfo(
                name=device_data[ATTR_NAME], model=device_data[ATTR_MODEL]
            )
            for device_id, device_data in sensor_update.devices.items()
        },
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): SensorEntityDescription(
                key=f"{device_key.key}_{device_key.device_id}",
                name=sensor_description.name,
                device_class=_sensor_device_class_to_hass(
                    sensor_description.device_class
                ),
                native_unit_of_measurement=sensor_description.native_unit_of_measurement,
                entity_registry_enabled_default=device_key.key != RSSI_KEY,
            )
            for device_key, sensor_description in sensor_update.entity_descriptions.items()
        },
        entity_data={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )
