"""
homeassistant.components.sensor.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Demo platform that has a couple of fake sensors.
"""
from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_CELCIUS, ATTR_BATTERY_LEVEL


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Demo sensors. """
    add_devices([
        DemoSensor('Outside Temperature', 15.6, TEMP_CELCIUS, 12),
        DemoSensor('Outside Humidity', 54, '%', None),
    ])


class DemoSensor(Entity):
    """ A Demo sensor. """

    def __init__(self, name, state, unit_of_measurement, battery):
        self._name = name
        self._state = state
        self._unit_of_measurement = unit_of_measurement
        self._battery = battery

    @property
    def should_poll(self):
        """ No polling needed for a demo sensor. """
        return False

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ Unit this state is expressed in. """
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """ Returns the state attributes. """
        if self._battery:
            return {
                ATTR_BATTERY_LEVEL: self._battery,
            }
