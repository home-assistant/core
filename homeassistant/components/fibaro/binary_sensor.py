"""Support for Fibaro binary sensors."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FIBARO_DEVICES, FibaroDevice
from .const import DOMAIN

SENSOR_TYPES = {
    "com.fibaro.floodSensor": ["Flood", "mdi:water", BinarySensorDeviceClass.MOISTURE],
    "com.fibaro.motionSensor": ["Motion", "mdi:run", BinarySensorDeviceClass.MOTION],
    "com.fibaro.doorSensor": ["Door", "mdi:window-open", BinarySensorDeviceClass.DOOR],
    "com.fibaro.windowSensor": [
        "Window",
        "mdi:window-open",
        BinarySensorDeviceClass.WINDOW,
    ],
    "com.fibaro.smokeSensor": ["Smoke", "mdi:smoking", BinarySensorDeviceClass.SMOKE],
    "com.fibaro.FGMS001": ["Motion", "mdi:run", BinarySensorDeviceClass.MOTION],
    "com.fibaro.heatDetector": ["Heat", "mdi:fire", BinarySensorDeviceClass.HEAT],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Fibaro controller devices."""
    async_add_entities(
        [
            FibaroBinarySensor(device)
            for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES][
                Platform.BINARY_SENSOR
            ]
        ],
        True,
    )


class FibaroBinarySensor(FibaroDevice, BinarySensorEntity):
    """Representation of a Fibaro Binary Sensor."""

    def __init__(self, fibaro_device: Any) -> None:
        """Initialize the binary_sensor."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)
        stype = None
        if fibaro_device.type in SENSOR_TYPES:
            stype = fibaro_device.type
        elif fibaro_device.baseType in SENSOR_TYPES:
            stype = fibaro_device.baseType
        if stype:
            self._attr_device_class = SENSOR_TYPES[stype][2]
            self._attr_icon = SENSOR_TYPES[stype][1]

    def update(self) -> None:
        """Get the latest data and update the state."""
        self._attr_is_on = self.current_binary_state
