"""
Support for Honeywell Lyric thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.lyric/
"""
import logging

import voluptuous as vol

from homeassistant.components.lyric import DATA_LYRIC
from homeassistant.components.climate import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, ClimateDevice,
    PLATFORM_SCHEMA, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE)
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT,
    CONF_SCAN_INTERVAL, STATE_ON, STATE_OFF, STATE_UNKNOWN)

DEPENDENCIES = ['lyric']
_LOGGER = logging.getLogger(__name__)

CONF_FAN = 'fan'
DEFAULT_FAN = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_FAN, default=DEFAULT_FAN): vol.Boolean
})

STATE_HEAT_COOL = 'heat-cool'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Lyric thermostat."""
    if discovery_info is None:
        return

    _LOGGER.debug("Setting up lyric thermostat")

    temp_unit = hass.config.units.temperature_unit

    has_fan = config.get(CONF_FAN)

    add_devices(
        [LyricThermostat(location, device, temp_unit, has_fan)
         for location, device in hass.data[DATA_LYRIC].thermostats()],
        True
    )


class LyricThermostat(ClimateDevice):
    """Representation of a Lyric thermostat."""

    def __init__(self, location, device, temp_unit, has_fan):
        """Initialize the thermostat."""
        self._unit = temp_unit
        self.location = location
        self.device = device

        # Not all lyric devices support cooling and heating remove unused
        self._operation_list = [STATE_OFF]

        # Add supported lyric thermostat features
        if self.device.can_heat:
            self._operation_list.append(STATE_HEAT)

        if self.device.can_cool:
            self._operation_list.append(STATE_COOL)
 
        if self.device.can_heat and self.device.can_cool:
            self._operation_list.append(STATE_AUTO)
 
        # feature of device
        self._has_fan = has_fan
        self._fan_list = self.device.settings["fan"]["allowedModes"]

        # data attributes
        self._away = None
        self._location = None
        self._name = None
        self._humidity = None
        self._target_temperature = None
        self._temperature = None
        self._temperature_scale = None
        self._target_temp_heat = None
        self._target_temp_cool = None
        self._dualSetpoint = None
        self._mode = None
        self._fan = None
        self._min_temperature = None
        self._max_temperature = None

    @property
    def name(self):
        """Return the name of the lyric, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_scale

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if self._mode in [STATE_HEAT, STATE_COOL, STATE_OFF]:
            return self._mode
        elif self._mode == STATE_HEAT_COOL:
            return STATE_AUTO
        else:
            return STATE_UNKNOWN

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if not self._dualSetpoint:
            return self._target_temperature
        else:
            return None

    @property
    def target_temperature_low(self):
        """Return the upper bound temperature we try to reach."""
        if self._dualSetpoint:
            return self._target_temp_cool
        else:
            return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self._dualSetpoint:
            return self._target_temp_heat
        else:
            return None

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if self._dualSetpoint:
            if target_temp_low is not None and target_temp_high is not None:
                temp = (target_temp_low, target_temp_high)
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("Lyric set_temperature-output-value=%s", temp)
        self.device.temperatureSetpoint = temp

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        _LOGGER.debug(operation_mode)        
        _LOGGER.debug(operation_mode.capitalize())        

        if operation_mode in [STATE_HEAT, STATE_COOL, STATE_OFF]:
            device_mode = operation_mode
        elif operation_mode == STATE_AUTO:
            device_mode = STATE_HEAT_COOL
        self.device.operationMode = device_mode.capitalize()

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    def turn_away_mode_on(self):
        """Turn away on."""
        #self.device.away = True

    def turn_away_mode_off(self):
        """Turn away off."""
        #self.device.away = False

    @property
    def current_fan_mode(self):
        """Return whether the fan is on."""
        if self._has_fan:
            # Return whether the fan is on
            return self._fan
        else:
            # No Fan available so disable slider
            return None

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    def set_fan_mode(self, fan):
        """Set fan state."""
        self.device.fan = fan

    @property
    def min_temp(self):
        """Identify min_temp in Lyric API or defaults if not available."""
        return self._min_temperature

    @property
    def max_temp(self):
        """Identify max_temp in Lyric API or defaults if not available."""
        return self._max_temperature

    def update(self):
        """Cache value from Python-lyric."""
        self._location = self.device.where
        self._name = self.device.name
        self._humidity = self.device.indoorHumidity
        self._temperature = self.device.indoorTemperature
        self._mode = self.device.operationMode.lower()
        self._target_temperature = self.device.temperatureSetpoint
        self._target_temp_heat = self.device.heatSetpoint
        self._target_temp_cool = self.device.coolSetpoint
        self._dualSetpoint = self.device.hasDualSetpointStatus
        self._fan = self.device.settings["fan"]["changeableValues"]["mode"]
        self._away = self.device.away
        self._min_temperature = self.device.minSetpoint
        self._max_temperature = self.device.maxSetpoint
        if self.device.units == 'Celsius':
            self._temperature_scale = TEMP_CELSIUS
        else:
            self._temperature_scale = TEMP_FAHRENHEIT
