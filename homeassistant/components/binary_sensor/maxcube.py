"""
Support for MAX! Window Shutter via MAX! Cube.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/maxcube/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.maxcube import DATA_KEY
from homeassistant.const import STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Iterate through all MAX! Devices and add window shutters."""
    devices = []
    for handler in hass.data[DATA_KEY].values():
        cube = handler.cube
        for device in cube.devices:
            name = "{} {}".format(
                cube.room_by_id(device.room_id).name, device.name)

            # Only add Window Shutters
            if cube.is_windowshutter(device):
                devices.append(
                    MaxCubeShutter(handler, name, device.rf_address))

    if devices:
        add_devices(devices)


class MaxCubeShutter(BinarySensorDevice):
    """Representation of a MAX! Cube Binary Sensor device."""

    def __init__(self, handler, name, rf_address):
        """Initialize MAX! Cube BinarySensorDevice."""
        self._name = name
        self._sensor_type = 'window'
        self._rf_address = rf_address
        self._cubehandle = handler
        self._state = STATE_UNKNOWN

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the BinarySensorDevice."""
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
