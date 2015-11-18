"""
homeassistant.components.sensor.ecobee
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This sensor component requires that the Ecobee Thermostat
component be setup first. This component shows remote
ecobee sensor data.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ecobee/
"""
from homeassistant.helpers.entity import Entity
import json
import logging
import os

DEPENDENCIES = ['thermostat']

SENSOR_TYPES = {
    'temperature': ['Temperature', '°F'],
    'humidity': ['Humidity', '%'],
    'occupancy': ['Occupancy', '']
}

_LOGGER = logging.getLogger(__name__)

ECOBEE_CONFIG_FILE = 'ecobee.conf'


def config_from_file(filename):
    ''' Small configuration file reading function '''
    if os.path.isfile(filename):
        try:
            with open(filename, 'r') as fdesc:
                return json.loads(fdesc.read())
        except IOError as error:
            _LOGGER.error("ecobee sensor couldn't read config file: " + error)
            return False
    else:
        return {}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors. """
    config = config_from_file(hass.config.path(ECOBEE_CONFIG_FILE))
    dev = list()
    for name, data in config['sensors'].items():
        if 'temp' in data:
            dev.append(EcobeeSensor(name, 'temperature', hass))
        if 'humidity' in data:
            dev.append(EcobeeSensor(name, 'humidity', hass))
        if 'occupancy' in data:
            dev.append(EcobeeSensor(name, 'occupancy', hass))

    add_devices(dev)


class EcobeeSensor(Entity):
    """ An ecobee sensor. """

    def __init__(self, sensor_name, sensor_type, hass):
        self._name = sensor_name + ' ' + SENSOR_TYPES[sensor_type][0]
        self.sensor_name = sensor_name
        self.hass = hass
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        return self._name.rstrip()

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    def update(self):
        config = config_from_file(self.hass.config.path(ECOBEE_CONFIG_FILE))
        try:
            data = config['sensors'][self.sensor_name]
            if self.type == 'temperature':
                self._state = data['temp']
            elif self.type == 'humidity':
                self._state = data['humidity']
            elif self.type == 'occupancy':
                self._state = data['occupancy']
        except KeyError:
            print("Error updating ecobee sensors.")
