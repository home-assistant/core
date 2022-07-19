"""The Govee Bluetooth integration."""
from __future__ import annotations

from govee_ble import (
    ATTR_HW_VERSION as SENSOR_HW_VERSION,
    ATTR_MANUFACTURER as SENSOR_MANUFACTURER,
    ATTR_MODEL as SENSOR_MODEL,
    ATTR_NAME as SENSOR_NAME,
    ATTR_SW_VERSION as SENSOR_SW_VERSION,
    SIGNAL_STRENGTH_KEY,
    DeviceClass,
    DeviceKey,
    SensorDeviceInfo,
    SensorUpdate,
)

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import (
    ATTR_HW_VERSION,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.entity import DeviceInfo

SENSOR_DEVICE_CLASS_TO_HASS = {
    DeviceClass.APPARENT_POWER: SensorDeviceClass.APPARENT_POWER,
    DeviceClass.BATTERY: SensorDeviceClass.BATTERY,
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


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def _sensor_device_class_to_hass(
    sensor_device_class: DeviceClass | None,
) -> SensorDeviceClass | None:
    """Convert a sensor device class to a sensor device class."""
    if sensor_device_class is None:
        return None
    return SENSOR_DEVICE_CLASS_TO_HASS.get(sensor_device_class)


def _sensor_device_info_to_hass(
    device_info: SensorDeviceInfo,
) -> DeviceInfo:
    """Convert a sensor device info to a sensor device info."""
    base_device_info = DeviceInfo({})
    if device_info.get(SENSOR_NAME) is not None:
        base_device_info[ATTR_NAME] = device_info[SENSOR_NAME]
    if device_info.get(SENSOR_MANUFACTURER) is not None:
        base_device_info[ATTR_MANUFACTURER] = device_info[SENSOR_MANUFACTURER]
    if device_info.get(SENSOR_SW_VERSION) is not None:
        base_device_info[ATTR_SW_VERSION] = device_info[SENSOR_HW_VERSION]
    if device_info.get(SENSOR_HW_VERSION) is not None:
        base_device_info[ATTR_HW_VERSION] = device_info[SENSOR_HW_VERSION]
    if device_info.get(SENSOR_MODEL) is not None:
        base_device_info[ATTR_MODEL] = device_info[SENSOR_MODEL]
    return base_device_info


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
            _device_key_to_bluetooth_entity_key(device_key): SensorEntityDescription(
                key=f"{device_key.key}_{device_key.device_id}",
                name=sensor_description.name,
                device_class=_sensor_device_class_to_hass(
                    sensor_description.device_class
                ),
                native_unit_of_measurement=sensor_description.native_unit_of_measurement,
                entity_registry_enabled_default=device_key.key != SIGNAL_STRENGTH_KEY,
            )
            for device_key, sensor_description in sensor_update.entity_descriptions.items()
        },
        entity_data={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )
