"""Support for Fibaro binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FIBARO_DEVICES, FibaroDevice
from .const import DOMAIN

SENSOR_TYPES = {
    "com.fibaro.floodSensor": ["Flood", "mdi:water", "flood"],
    "com.fibaro.motionSensor": ["Motion", "mdi:run", BinarySensorDeviceClass.MOTION],
    "com.fibaro.doorSensor": ["Door", "mdi:window-open", BinarySensorDeviceClass.DOOR],
    "com.fibaro.windowSensor": [
        "Window",
        "mdi:window-open",
        BinarySensorDeviceClass.WINDOW,
    ],
    "com.fibaro.smokeSensor": ["Smoke", "mdi:smoking", BinarySensorDeviceClass.SMOKE],
    "com.fibaro.FGMS001": ["Motion", "mdi:run", BinarySensorDeviceClass.MOTION],
    "com.fibaro.heatDetector": ["Heat", "mdi:fire", "heat"],
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
                "binary_sensor"
            ]
        ],
        True,
    )


class FibaroBinarySensor(FibaroDevice, BinarySensorEntity):
    """Representation of a Fibaro Binary Sensor."""

    def __init__(self, fibaro_device):
        """Initialize the binary_sensor."""
        self._state = None
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)
        stype = None
        if fibaro_device.type in SENSOR_TYPES:
            stype = fibaro_device.type
        elif fibaro_device.baseType in SENSOR_TYPES:
            stype = fibaro_device.baseType
        if stype:
            self._device_class = SENSOR_TYPES[stype][2]
            self._icon = SENSOR_TYPES[stype][1]
        else:
            self._device_class = None
            self._icon = None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        self._state = self.current_binary_state
