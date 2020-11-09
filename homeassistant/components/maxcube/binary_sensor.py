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
        cube = handler.cube
        for device in cube.devices:
            name = f"{cube.room_by_id(device.room_id).name} {device.name}"

            # Only add Window Shutters
            if cube.is_windowshutter(device):
                devices.append(MaxCubeShutter(handler, name, device.rf_address))

    if devices:
        add_entities(devices)


class MaxCubeShutter(BinarySensorEntity):
    """Representation of a MAX! Cube Binary Sensor device."""

    def __init__(self, handler, name, rf_address):
        """Initialize MAX! Cube BinarySensorEntity."""
        self._name = name
        self._sensor_type = DEVICE_CLASS_WINDOW
        self._rf_address = rf_address
        self._cubehandle = handler
        self._state = None

    @property
    def name(self):
        """Return the name of the BinarySensorEntity."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def is_on(self):
        """Return true if the binary sensor is on/open."""
        return self._state

    def update(self):
        """Get latest data from MAX! Cube."""
        self._cubehandle.update()
        device = self._cubehandle.cube.device_by_rf(self._rf_address)
        self._state = device.is_open
