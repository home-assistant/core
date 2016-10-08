"""
Support for Nest thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.nest/
"""
import logging
import voluptuous as vol
import homeassistant.components.nest as nest
from homeassistant.components.climate import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, ClimateDevice,
    PLATFORM_SCHEMA, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE)
from homeassistant.const import (
    TEMP_CELSIUS, CONF_SCAN_INTERVAL, STATE_ON, STATE_OFF, STATE_UNKNOWN)

DEPENDENCIES = ['nest']
_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Nest thermostat."""
    temp_unit = hass.config.units.temperature_unit
    add_devices([NestThermostat(structure, device, temp_unit)
                 for structure, device in nest.devices()])


# pylint: disable=abstract-method,too-many-public-methods
class NestThermostat(ClimateDevice):
    """Representation of a Nest thermostat."""

    def __init__(self, structure, device, temp_unit):
        """Initialize the thermostat."""
        self._unit = temp_unit
        self.structure = structure
        self.device = device
        self._fan_list = [STATE_ON, STATE_AUTO]
        self._operation_list = [STATE_HEAT, STATE_COOL, STATE_AUTO,
                                STATE_OFF]

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
        }

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.device.temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self.device.mode == 'cool':
            return STATE_COOL
        elif self.device.mode == 'heat':
            return STATE_HEAT
        elif self.device.mode == 'range':
            return STATE_AUTO
        elif self.device.mode == 'off':
            return STATE_OFF
        else:
            return STATE_UNKNOWN

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.device.mode != 'range' and not self.is_away_mode_on:
            return self.device.target
        else:
            return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.is_away_mode_on and self.device.away_temperature[0]:
            # away_temperature is always a low, high tuple
            return self.device.away_temperature[0]
        if self.device.mode == 'range':
            return self.device.target[0]
        else:
            return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self.is_away_mode_on and self.device.away_temperature[1]:
            # away_temperature is always a low, high tuple
            return self.device.away_temperature[1]
        if self.device.mode == 'range':
            return self.device.target[1]
        else:
            return None

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self.structure.away

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if target_temp_low is not None and target_temp_high is not None:

            if self.device.mode == 'range':
                temp = (target_temp_low, target_temp_high)
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("Nest set_temperature-output-value=%s", temp)
        self.device.target = temp

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if operation_mode == STATE_HEAT:
            self.device.mode = 'heat'
        elif operation_mode == STATE_COOL:
            self.device.mode = 'cool'
        elif operation_mode == STATE_AUTO:
            self.device.mode = 'range'
        elif operation_mode == STATE_OFF:
            self.device.mode = 'off'

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    def turn_away_mode_on(self):
        """Turn away on."""
        self.structure.away = True

    def turn_away_mode_off(self):
        """Turn away off."""
        self.structure.away = False

    @property
    def current_fan_mode(self):
        """Return whether the fan is on."""
        return STATE_ON if self.device.fan else STATE_AUTO

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    def set_fan_mode(self, fan):
        """Turn fan on/off."""
        self.device.fan = fan.lower()

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
