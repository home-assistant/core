"""
homeassistant.components.sensor.nest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Nest Thermostat Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nest/
"""
from homeassistant.helpers.entity import Entity
from homeassistant.const import (STATE_ON, STATE_OFF, TEMP_CELCIUS)
from homeassistant.helpers.temperature import convert

import homeassistant.components.nest as nest
import logging
import socket

DEPENDENCIES = ['nest']
SENSOR_TYPES = ['humidity',
                'mode',
                'last_ip',
                'local_ip',
                'last_connection',
                'battery_level']

BINARY_TYPES = ['fan',
                'hvac_ac_state',
                'hvac_aux_heater_state',
                'hvac_heat_x2_state',
                'hvac_heat_x3_state',
                'hvac_alt_heat_state',
                'hvac_alt_heat_x2_state',
                'hvac_emer_heat_state',
                'online']

SENSOR_UNITS = {'humidity': '%', 'battery_level': '%'}

SENSOR_TEMP_TYPES = ['temperature',
                     'target',
                     'away_temperature[0]',
                     'away_temperature[1]']

def setup_platform(hass, config, add_devices, discovery_info=None):
    logger = logging.getLogger(__name__)
    try:
        for structure in nest.NEST.structures:
            for device in structure.devices:
                for variable in config['monitored_conditions']:
                    if variable in SENSOR_TYPES:
                        add_devices([NestSensor(structure, device, variable)])
                    elif variable in BINARY_TYPES:
                        add_devices([NestBinarySensor(structure, device, variable)])
                    elif variable in SENSOR_TEMP_TYPES:
                        add_devices([NestTempSensor(structure, device, variable)])
                    else:
                        logger.error('Nest sensor type: "%s" does not exist', variable)
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
            return name + ' ' + self.variable
        else:
            if name == '':
                return location.capitalize() + ' ' + self.variable
            else:
                return location.capitalize() + '(' + name + ')' + self.variable
    @property
    def state(self):
        """ Returns the state of the sensor. """
        return getattr(self.device, self.variable)

    @property
    def unit_of_measurement(self):
        return SENSOR_UNITS.get(self.variable, None)

class NestTempSensor(NestSensor):
    """ Represents a Nest Temperature sensor. """

    @property
    def unit_of_measurement(self):
        return self.hass.config.temperature_unit

    @property
    def state(self):
        temp = getattr(self.device, self.variable)
        if temp is None:
            return None

        value = convert(temp, TEMP_CELCIUS,
                        self.hass.config.temperature_unit)

        return round(value, 1)

class NestBinarySensor(NestSensor):
    """ Represents a Nst Binary sensor. """

    @property
    def state(self):
        if getattr(self.device, self.variable):
            return STATE_ON
        else:
            return STATE_OFF
