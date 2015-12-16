"""
homeassistant.components.sensor.tellduslive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shows sensor values from Tellstick Net/Telstick Live.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tellduslive/

Tellstick Net devices can be auto discovered using the method described in:
https://developer.telldus.com/doxygen/html/TellStickNet.html

Also, it should be possible to communicate with the Tellstick Net device
directly, bypassing the Tellstick Live service. This however is poorly documented.

"""
import logging

from homeassistant.const import TEMP_CELCIUS
from homeassistant.helpers.entity import Entity
import homeassistant.util as util

REQUIREMENTS = ['tellive-py==0.5.2']

def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up Tellstick sensors. """
    pass


class TelldusLiveSensor(Entity):
    """ Represents a Telldus Live sensor. """

    def __init__(self, name, sensor, datatype, sensor_info):
        self.datatype = datatype
        self.sensor = sensor
        self._unit_of_measurement = sensor_info.unit or None
        self._name = "{} {}".format(name, sensor_info.name)

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self.sensor.value(self.datatype).value

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement
