"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import Optional, Union

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import ATTR_MANUFACTURER, ATTR_MODEL, ATTR_NAME, TIME_SECONDS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = {
    (SensorDeviceClass.TEMPERATURE, TIME_SECONDS): SensorEntityDescription(
        key=f"{SensorDeviceClass.TEMPERATURE}_{TIME_SECONDS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TIME_SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            OralBBluetoothSensorEntity, async_add_entities
        )
    )
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entry.async_on_unload(coordinator.async_register_processor(processor))
    # async_add_entities(
    #     OralBSensor(coordinator, processor, description)
    #     for description in SENSORS
    # )


def device_key_to_bluetooth_entity_key(
    device_key,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def sensor_device_info_to_hass(
    sensor_device_info,
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
    sensor_update,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate()


class OralBBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[Optional[Union[float, int]]]
    ],
    SensorEntity,
):
    """Representation of a Tilt Hydrometer BLE sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
