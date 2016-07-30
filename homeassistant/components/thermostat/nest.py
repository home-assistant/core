"""
Support for Nest thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/thermostat.nest/
"""
import voluptuous as vol

import homeassistant.components.nest as nest
from homeassistant.components.thermostat import (
    STATE_COOL, STATE_HEAT, STATE_IDLE, ThermostatDevice)
from homeassistant.const import TEMP_CELSIUS, CONF_PLATFORM, CONF_SCAN_INTERVAL

DEPENDENCIES = ['nest']

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): nest.DOMAIN,
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Nest thermostat."""
    add_devices([NestThermostat(structure, device)
                 for structure, device in nest.devices()])


# pylint: disable=abstract-method
class NestThermostat(ThermostatDevice):
    """Representation of a Nest thermostat."""

    def __init__(self, structure, device):
        """Initialize the thermostat."""
        self.structure = structure
        self.device = device

    @property
    def name(self):
        """Return the name of the nest, if any."""
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
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        # Move these to Thermostat Device and make them global
        return {
            "humidity": self.device.humidity,
            "target_humidity": self.device.target_humidity,
            "mode": self.device.mode
        }

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.device.temperature

    @property
    def operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self.device.hvac_ac_state is True:
            return STATE_COOL
        elif self.device.hvac_heater_state is True:
            return STATE_HEAT
        else:
            return STATE_IDLE

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.device.mode == 'range':
            low, high = self.target_temperature_low, \
                        self.target_temperature_high
            if self.operation == STATE_COOL:
                temp = high
            elif self.operation == STATE_HEAT:
                temp = low
            else:
                # If the outside temp is lower than the current temp, consider
                # the 'low' temp to the target, otherwise use the high temp
                if (self.device.structure.weather.current.temperature <
                        self.current_temperature):
                    temp = low
                else:
                    temp = high
        else:
            if self.is_away_mode_on:
                # away_temperature is a low, high tuple. Only one should be set
                # if not in range mode, the other will be None
                temp = self.device.away_temperature[0] or \
                        self.device.away_temperature[1]
            else:
                temp = self.device.target

        return temp

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.is_away_mode_on and self.device.away_temperature[0]:
            # away_temperature is always a low, high tuple
            return self.device.away_temperature[0]
        if self.device.mode == 'range':
            return self.device.target[0]
        return self.target_temperature

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self.is_away_mode_on and self.device.away_temperature[1]:
            # away_temperature is always a low, high tuple
            return self.device.away_temperature[1]
        if self.device.mode == 'range':
            return self.device.target[1]
        return self.target_temperature

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self.structure.away

    def set_temperature(self, temperature):
        """Set new target temperature."""
        if self.device.mode == 'range':
            if self.target_temperature == self.target_temperature_low:
                temperature = (temperature, self.target_temperature_high)
            elif self.target_temperature == self.target_temperature_high:
                temperature = (self.target_temperature_low, temperature)
        self.device.target = temperature

    def set_hvac_mode(self, hvac_mode):
        """Set hvac mode."""
        self.device.mode = hvac_mode

    def turn_away_mode_on(self):
        """Turn away on."""
        self.structure.away = True

    def turn_away_mode_off(self):
        """Turn away off."""
        self.structure.away = False

    @property
    def is_fan_on(self):
        """Return whether the fan is on."""
        return self.device.fan

    def turn_fan_on(self):
        """Turn fan on."""
        self.device.fan = True

    def turn_fan_off(self):
        """Turn fan off."""
        self.device.fan = False

    @property
    def min_temp(self):
        """Identify min_temp in Nest API or defaults if not available."""
        temp = self.device.away_temperature.low
        if temp is None:
            return super().min_temp
        else:
            return temp

    @property
    def max_temp(self):
        """Identify max_temp in Nest API or defaults if not available."""
        temp = self.device.away_temperature.high
        if temp is None:
            return super().max_temp
        else:
            return temp

    def update(self):
        """Python-nest has its own mechanism for staying up to date."""
        pass
