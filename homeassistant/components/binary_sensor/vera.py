"""
Support for Vera binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.vera/
"""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, ENTITY_ID_FORMAT)
from homeassistant.components.vera import (
    VERA_CONTROLLER, VERA_DEVICES, VeraDevice)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Perform the setup for Vera controller devices."""
    add_devices(
        VeraBinarySensor(device, hass.data[VERA_CONTROLLER])
        for device in hass.data[VERA_DEVICES]['binary_sensor'])


class VeraBinarySensor(VeraDevice, BinarySensorDevice):
    """Representation of a Vera Binary Sensor."""

    def __init__(self, vera_device, controller):
        """Initialize the binary_sensor."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        self._state = self.vera_device.is_tripped
