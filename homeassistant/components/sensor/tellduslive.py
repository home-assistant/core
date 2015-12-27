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


_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['tellduslive']

SENSOR_TYPE_TEMP = "temp"
SENSOR_TYPE_HUMIDITY = "humidity"

SENSOR_TYPES = {
    SENSOR_TYPE_TEMP: ['Temperature', TEMP_CELCIUS, "mdi:thermometer"],
    SENSOR_TYPE_HUMIDITY: ['Humidity', '%', "mdi:water"],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up Tellstick sensors. """
    sensors = tellduslive.NETWORK.get_sensors()
    devices = []
    print(sensors)
    for component in sensors:
        for sensor in component["data"]:
            # one component can have more than one sensor
            # (e.g. humidity and temperature)
            devices.append(TelldusLiveSensor(component["id"],
                                             component["name"],
                                             sensor["name"]))
    add_devices(devices)


class TelldusLiveSensor(Entity):
    """ Represents a Telldus Live sensor. """

    def __init__(self, sensor_id, sensor_name, sensor_type):
        self._sensor_id = sensor_id
        self._sensor_type = sensor_type
        self._state = None
        self._name = sensor_name + ' ' + SENSOR_TYPES[sensor_type][0]
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
        return SENSOR_TYPES[self._sensor_type][1]

    @property
    def icon(self):
        return SENSOR_TYPES[self._sensor_type][2]

    def update(self):
        self._state = tellduslive.NETWORK.get_sensor_value(self._sensor_id,
                                                           self._sensor_type)
        self._state = float(self._state)
        if self._sensor_type == SENSOR_TYPE_TEMP:
            self._state = round(self._state, 1)
        elif self._sensor_type == SENSOR_TYPE_HUMIDITY:
            self._state = int(round(self._state))
