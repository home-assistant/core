"""
homeassistant.components.sensor.nest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Nest Thermostat Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nest/
"""
import logging
import socket
import homeassistant.components.nest as nest

from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_CELCIUS

DEPENDENCIES = ['nest']
SENSOR_TYPES = ['humidity',
                'mode',
                'last_ip',
                'local_ip',
                'last_connection',
                'battery_level']

SENSOR_UNITS = {'humidity': '%', 'battery_level': 'V'}

SENSOR_TEMP_TYPES = ['temperature',
                     'target',
                     'away_temperature[0]',
                     'away_temperature[1]']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup Nest Sensor. """

    logger = logging.getLogger(__name__)
    try:
        for structure in nest.NEST.structures:
            for device in structure.devices:
                for variable in config['monitored_conditions']:
                    if variable in SENSOR_TYPES:
                        add_devices([NestBasicSensor(structure,
                                                     device,
                                                     variable)])
                    elif variable in SENSOR_TEMP_TYPES:
                        add_devices([NestTempSensor(structure,
                                                    device,
                                                    variable)])
                    else:
                        logger.error('Nest sensor type: "%s" does not exist',
                                     variable)
    except socket.error:
        logger.error(
            "Connection error logging into the nest web service."
        )


class NestSensor(Entity):
    """ Represents a Nest sensor. """

    def __init__(self, structure, device, variable):
        self.structure = structure
        self.device = device
        self.variable = variable

    @property
    def name(self):
        """ Returns the name of the nest, if any. """

        location = self.device.where
        name = self.device.name
        if location is None:
            return "{} {}".format(name, self.variable)
        else:
            if name == '':
                return "{} {}".format(location.capitalize(), self.variable)
            else:
                return "{}({}){}".format(location.capitalize(),
                                         name,
                                         self.variable)


class NestBasicSensor(NestSensor):
    """ Represents a basic Nest sensor with state. """

    @property
    def state(self):
        """ Returns the state of the sensor. """
        return getattr(self.device, self.variable)

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return SENSOR_UNITS.get(self.variable, None)


class NestTempSensor(NestSensor):
    """ Represents a Nest Temperature sensor. """

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return TEMP_CELCIUS

    @property
    def state(self):
        """ Returns the state of the sensor. """
        temp = getattr(self.device, self.variable)
        if temp is None:
            return None

        return round(temp, 1)
