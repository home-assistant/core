"""
homeassistant.components.sensor.tellduslive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shows sensor values from Tellstick Net/Telstick Live.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tellduslive/

"""
import logging

from homeassistant.const import TEMP_CELCIUS
from homeassistant.helpers.entity import Entity
from homeassistant.components import tellduslive
import homeassistant.util as util

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['tellduslive']

SENSOR_TYPES = {
    'temp': ['Temperature', TEMP_CELCIUS],
    'humidity': ['Humidity', '%'],
}

def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up Tellstick sensors. """
    sensors = tellduslive.NETWORK.get_sensors()
    # fixme: metadata groups etc
    devices = []
    for component in sensors:
        for sensor in component["data"]:
            # one component can have more than one sensor 
            # (e.g. humidity and temperature)
            unit_of_measurement = SENSOR_TYPES[sensor["name"]]
            devices.append(TelldusLiveSensor(component["id"],
                                             component["name"],
                                             sensor["name"]))
    add_devices(devices)


class TelldusLiveSensor(Entity):
    """ Represents a Telldus Live sensor. """

    def __init__(self, sensor_id, sensor_name, sensor_type):
        self.sensor_id = sensor_id
        self.sensor_type = sensor_type
        self._state = None
        self._name = sensor_name + ' ' + SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

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
        return self._unit_of_measurement

    def update(self):
        sensors = tellduslive.NETWORK.get_sensors()
        for component in sensors:
            for sensor in component["data"]:
                if component["id"] == self.sensor_id and sensor["name"] == self.sensor_type:
                    self._state = int(round(float(sensor["value"])))

