"""
Support for Vera binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.vera/
"""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDevice)
from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Perform the setup for Vera controller devices."""
    add_devices_callback(
        VeraBinarySensor(device, VERA_CONTROLLER)
        for device in VERA_DEVICES['binary_sensor'])


class VeraBinarySensor(VeraDevice, BinarySensorDevice):
    """Representation of a Vera Binary Sensor."""

    def __init__(self, vera_device, controller):
        """Initialize the binary_sensor."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        self._state = self.vera_device.is_tripped
