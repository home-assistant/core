"""Support for MAX! binary sensors via MAX! Cube."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_WINDOW,
    BinarySensorEntity,
)

from . import DATA_KEY


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Iterate through all MAX! Devices and add window shutters."""
    devices = []
    for handler in hass.data[DATA_KEY].values():
        for device in handler.cube.devices:
            # Only add Window Shutters
            if device.is_windowshutter():
                devices.append(MaxCubeShutter(handler, device))

    if devices:
        add_entities(devices)


class MaxCubeShutter(BinarySensorEntity):
    """Representation of a MAX! Cube Binary Sensor device."""

    def __init__(self, handler, device):
        """Initialize MAX! Cube BinarySensorEntity."""
        room = handler.cube.room_by_id(device.room_id)
        self._name = f"{room.name} {device.name}"
        self._cubehandle = handler
        self._device = device

    @property
    def name(self):
        """Return the name of the BinarySensorEntity."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device.serial

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEVICE_CLASS_WINDOW

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._device.is_open

    def update(self):
        """Get latest data from MAX! Cube."""
        self._cubehandle.update()
