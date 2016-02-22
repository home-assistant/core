"""
Demo platform that has two fake binary sensors.
"""
from homeassistant.components.binary_sensor import BinarySensorDevice


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Sets up the Demo binary sensors """
    add_devices([
        DemoBinarySensor('Basement Floor Wet', False, 'moisture'),
        DemoBinarySensor('Movement Backyard', True, 'motion'),
    ])


class DemoBinarySensor(BinarySensorDevice):
    """A Demo binary sensor."""

    def __init__(self, name, state, sensor_class):
        self._name = name
        self._state = state
        self._sensor_type = sensor_class

    @property
    def sensor_class(self):
        """Return the class of this sensor."""
        return self._sensor_type

    @property
    def should_poll(self):
        """No polling needed for a demo binary sensor."""
        return False

    @property
    def name(self):
        """Returns the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """True if the binary sensor is on."""
        return self._state
