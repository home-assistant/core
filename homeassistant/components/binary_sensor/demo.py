"""
homeassistant.components.binary_sensor.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Demo platform that has two fake binary sensors.
"""
from homeassistant.components.binary_sensor import BinarySensorDevice


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Demo binary sensors. """
    add_devices([
        DemoBinarySensor('Window Bathroom', True, None),
        DemoBinarySensor('Floor Basement', False, None),
    ])


class DemoBinarySensor(BinarySensorDevice):
    """ A Demo binary sensor. """

    def __init__(self, name, state, icon=None):
        self._name = name
        self._state = state
        self._icon = icon

    @property
    def should_poll(self):
        """ No polling needed for a demo binary sensor. """
        return False

    @property
    def name(self):
        """ Returns the name of the binary sensor. """
        return self._name

    @property
    def icon(self):
        """ Returns the icon to use for device if any. """
        return self._icon

    @property
    def is_on(self):
        """ True if the binary sensor is on. """
        return self._state
