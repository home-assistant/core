"""
homeassistant.components.thermostat.nest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds support for Nest thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.nest/
"""
import logging
import socket

import homeassistant.components.nest as nest
from homeassistant.components.thermostat import (
    STATE_COOL, STATE_HEAT, STATE_IDLE, ThermostatDevice)
from homeassistant.const import TEMP_CELCIUS

DEPENDENCIES = ['nest']


def setup_platform(hass, config, add_devices, discovery_info=None):
    "Setup nest thermostat"

    logger = logging.getLogger(__name__)

    try:
        add_devices([
            NestThermostat(structure, device)
            for structure in nest.NEST.structures
            for device in structure.devices
        ])
    except socket.error:
        logger.error(
            "Connection error logging into the nest web service."
        )


class NestThermostat(ThermostatDevice):
    """ Represents a Nest thermostat. """

    def __init__(self, structure, device):
        self.structure = structure
        self.device = device

    @property
    def name(self):
        """ Returns the name of the nest, if any. """
        location = self.device.where
        name = self.device.name
        if location is None:
            return name
        else:
            if name == '':
                return location.capitalize()
            else:
                return location.capitalize() + '(' + name + ')'

    @property
    def unit_of_measurement(self):
        """ Unit of measurement this thermostat expresses itself in. """
        return TEMP_CELCIUS

    @property
    def device_state_attributes(self):
        """ Returns device specific state attributes. """
        # Move these to Thermostat Device and make them global
        return {
            "humidity": self.device.humidity,
            "target_humidity": self.device.target_humidity,
            "mode": self.device.mode
        }

    @property
    def current_temperature(self):
        """ Returns the current temperature. """
        return round(self.device.temperature, 1)

    @property
    def operation(self):
        """ Returns current operation ie. heat, cool, idle """
        if self.device.hvac_ac_state is True:
            return STATE_COOL
        elif self.device.hvac_heater_state is True:
            return STATE_HEAT
        else:
            return STATE_IDLE

    @property
    def target_temperature(self):
        """ Returns the temperature we try to reach. """
        target = self.device.target

        if self.device.mode == 'range':
            low, high = target
            if self.operation == STATE_COOL:
                temp = high
            elif self.operation == STATE_HEAT:
                temp = low
            else:
                range_average = (low + high)/2
                if self.current_temperature < range_average:
                    temp = low
                elif self.current_temperature >= range_average:
                    temp = high
        else:
            temp = target

        return round(temp, 1)

    @property
    def target_temperature_low(self):
        """ Returns the lower bound temperature we try to reach. """
        if self.device.mode == 'range':
            return round(self.device.target[0], 1)
        return round(self.target_temperature, 1)

    @property
    def target_temperature_high(self):
        """ Returns the upper bound temperature we try to reach. """
        if self.device.mode == 'range':
            return round(self.device.target[1], 1)
        return round(self.target_temperature, 1)

    @property
    def is_away_mode_on(self):
        """ Returns if away mode is on. """
        return self.structure.away

    def set_temperature(self, temperature):
        """ Set new target temperature """
        if self.device.mode == 'range':
            if self.target_temperature == self.target_temperature_low:
                temperature = (temperature, self.target_temperature_high)
            elif self.target_temperature == self.target_temperature_high:
                temperature = (self.target_temperature_low, temperature)
        self.device.target = temperature

    def turn_away_mode_on(self):
        """ Turns away on. """
        self.structure.away = True

    def turn_away_mode_off(self):
        """ Turns away off. """
        self.structure.away = False

    @property
    def is_fan_on(self):
        """ Returns whether the fan is on """
        return self.device.fan

    def turn_fan_on(self):
        """ Turns fan on """
        self.device.fan = True

    def turn_fan_off(self):
        """ Turns fan off """
        self.device.fan = False

    @property
    def min_temp(self):
        """ Identifies min_temp in Nest API or defaults if not available. """
        temp = self.device.away_temperature.low
        if temp is None:
            return super().min_temp
        else:
            return temp

    @property
    def max_temp(self):
        """ Identifies mxn_temp in Nest API or defaults if not available. """
        temp = self.device.away_temperature.high
        if temp is None:
            return super().max_temp
        else:
            return temp

    def update(self):
        """ Python-nest has its own mechanism for staying up to date. """
        pass
