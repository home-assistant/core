"""
Support for Fibaro binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.fibaro/
"""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, ENTITY_ID_FORMAT)
from homeassistant.components.fibaro import (
    FIBARO_CONTROLLER, FIBARO_DEVICES, FibaroDevice)

DEPENDENCIES = ['fibaro']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Perform the setup for Fibaro controller devices."""
    add_entities(
        [FibaroBinarySensor(device, hass.data[FIBARO_CONTROLLER])
         for device in hass.data[FIBARO_DEVICES]['binary_sensor']], True)


class FibaroBinarySensor(FibaroDevice, BinarySensorDevice):
    """Representation of a Fibaro Binary Sensor."""

    def __init__(self, fibaro_device, controller):
        """Initialize the binary_sensor."""
        self._state = None
        self.last_changed_time = None
        FibaroDevice.__init__(self, fibaro_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.fibaro_id)

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        if self.fibaro_device.properties.value == "false":
            self._state = False
        else:
            self._state = True
