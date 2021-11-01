"""Support for MAX! binary sensors via MAX! Cube."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
)
from homeassistant.const import ENTITY_CATEGORY_DIAGNOSTIC

from . import DATA_KEY


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Iterate through all MAX! Devices and add window shutters."""
    devices = []
    for handler in hass.data[DATA_KEY].values():
        for device in handler.cube.devices:
            devices.append(MaxCubeBattery(handler, device))
            # Only add Window Shutters
            if device.is_windowshutter():
                devices.append(MaxCubeShutter(handler, device))

    if devices:
        add_entities(devices)


class MaxCubeBinarySensorBase(BinarySensorEntity):
    def __init__(self, handler, device):
        """Initialize MAX! Cube BinarySensorEntity."""
        self._cubehandle = handler
        self._device = device
        self._room = handler.cube.room_by_id(device.room_id)
        self._attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC

    def update(self):
        """Get latest data from MAX! Cube."""
        self._cubehandle.update()


class MaxCubeShutter(MaxCubeBinarySensorBase):
    """Representation of a MAX! Cube Binary Sensor device."""

    def __init__(self, handler, device):
        """Initialize MAX! Cube BinarySensorEntity."""
        super().__init__(handler, device)

        self._attr_name = f"{self._room.name} {self._device.name}"
        self._attr_unique_id = self._device.serial
        self._attr_device_class = DEVICE_CLASS_WINDOW

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._device.is_open


class MaxCubeBattery(MaxCubeBinarySensorBase):
    """Representation of a MAX! Cube Binary Sensor device."""

    def __init__(self, handler, device):
        """Initialize MAX! Cube BinarySensorEntity."""
        super().__init__(handler, device)

        self._attr_name = f"{self._room.name} {device.name} battery"
        self._attr_unique_id = f"{self._device.serial}_battery"
        self._attr_device_class = DEVICE_CLASS_BATTERY

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._device.battery == 1
