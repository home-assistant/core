"""
Support for Nest thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.nest/
"""
import logging
import voluptuous as vol
import homeassistant.components.nest as nest
from homeassistant.components.climate import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, STATE_IDLE, ClimateDevice,
    PLATFORM_SCHEMA, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW)
from homeassistant.const import (
    TEMP_CELSIUS, CONF_SCAN_INTERVAL, STATE_ON, TEMP_FAHRENHEIT)
from homeassistant.util.temperature import convert as convert_temperature

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


# pylint: disable=abstract-method
class NestThermostat(ClimateDevice):
    """Representation of a Nest thermostat."""

    def __init__(self, structure, device, temp_unit):
        """Initialize the thermostat."""
        self._unit = temp_unit
        self.structure = structure
        self.device = device
        self._fan_list = [STATE_ON, STATE_AUTO]

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
        if self.device.measurment_scale == 'F':
            return TEMP_FAHRENHEIT
        elif self.device.measurement_scale == 'C':
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

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TARGET_TEMP_LOW) is not None and \
           kwargs.get(ATTR_TARGET_TEMP_HIGH) is not None:
            target_temp_high = convert_temperature(kwargs.get(
                ATTR_TARGET_TEMP_HIGH), self._unit, TEMP_CELSIUS)
            target_temp_low = convert_temperature(kwargs.get(
                ATTR_TARGET_TEMP_LOW), self._unit, TEMP_CELSIUS)

        temp = (target_temp_low, target_temp_high)
        _LOGGER.debug("Nest set_temperature-output-value=%s", temp)
        self.device.target = temp

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        self.device.mode = operation_mode

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
