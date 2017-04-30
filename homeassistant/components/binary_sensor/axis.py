"""
Support for Axis binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.axis/
"""
import logging

from homeassistant.components.binary_sensor import (BinarySensorDevice)
from homeassistant.components.axis import (AxisDeviceEvent)

DEPENDENCIES = ['axis']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Axis device event."""
    add_devices([AxisBinarySensor(discovery_info['axis_event'], hass)], True)


class AxisBinarySensor(AxisDeviceEvent, BinarySensorDevice):
    """Representation of a binary Axis event."""

    def __init__(self, axis_event, hass):
        """Initialize the binary sensor."""
        self._state = False
        self.hass = hass
        AxisDeviceEvent.__init__(self, axis_event)

    @property
    def is_on(self):
        """Return true if event is active."""
        return self._state

    def update(self):
        """Get the latest data and update the state."""
        self._state = self.axis_event.is_tripped
