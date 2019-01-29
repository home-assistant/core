"""
Support for the Lennox iComfort WiFi thermostat.

Sample entry for configuration.yaml:

climate:
  - platform: myicomfort
    name: Downstairs
    username: YOUR_MYICOMFORT_USERNAME
    password: YOUR_MYICOMFORY_PASSWORD

"""

import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    ClimateDevice, PLATFORM_SCHEMA, STATE_AUTO,
    STATE_COOL, STATE_HEAT, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW,
    SUPPORT_OPERATION_MODE, SUPPORT_AWAY_MODE, SUPPORT_FAN_MODE)
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    STATE_ON, STATE_OFF, STATE_IDLE, ATTR_TEMPERATURE)

REQUIREMENTS = ['myicomfort==0.2.0']

_LOGGER = logging.getLogger(__name__)

# HA doesn't have a 'circulate' state defined.
STATE_CIRCULATE = 'circulate'

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_TARGET_TEMPERATURE_HIGH |
                 SUPPORT_TARGET_TEMPERATURE_LOW |
                 SUPPORT_OPERATION_MODE |
                 SUPPORT_AWAY_MODE |
                 SUPPORT_FAN_MODE)

FAN_MODES = [
    STATE_AUTO, STATE_ON, STATE_CIRCULATE
]

OP_MODES = [
    STATE_OFF, STATE_HEAT, STATE_COOL, STATE_AUTO
]

SYSTEM_STATES = [
    STATE_IDLE, STATE_HEAT, STATE_COOL
]

TEMP_UNITS = [
    TEMP_FAHRENHEIT, TEMP_CELSIUS
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional('name', default='iComfort'): cv.string,
    vol.Optional('system', default=0): vol.Coerce(int),
    vol.Optional('zone', default=0): vol.Coerce(int),
    vol.Optional('min_temp'): vol.Coerce(float),
    vol.Optional('max_temp'): vol.Coerce(float),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the climate platform."""
    from myicomfort.api import Tstat

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    system = config.get('system')
    zone = config.get('zone')
    name = config.get('name')
    min_temp = config.get('min_temp')
    max_temp = config.get('max_temp')

    climate = [MyiComfortClimate(name, min_temp, max_temp,
                                 Tstat(username, password, system, zone))]

    add_devices(climate, True)


class MyiComfortClimate(ClimateDevice):
    """Class for Lennox iComfort WiFi thermostat."""

    def __init__(self, name, min_temp, max_temp, api):
        """Initialize the climate device."""
        self._name = name
        self._api = api
        self._min_temp = min_temp
        self._max_temp = max_temp

    def update(self):
        """Update data from the thermostat API."""
        self._api.pull_status()

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {
        }

    @property
    def state(self):
        """Return the current operational state."""
        return SYSTEM_STATES[self._api.state]

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_UNITS[self._api.temperature_units]

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self._min_temp:
            return self._min_temp
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self._max_temp:
            return self._max_temp
        return super().max_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._api.op_mode == 1:
            return min(self._api.set_points)
        if self._api.op_mode == 2:
            return max(self._api.set_points)
        return None

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._api.current_temperature

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        if self._api.op_mode == 3:
            return max(self._api.set_points)
        return None

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        if self._api.op_mode == 3:
            return min(self._api.set_points)
        return None

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._api.current_humidity

    @property
    def current_operation(self):
        """Return the current operation mode."""
        return OP_MODES[self._api.op_mode]

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OP_MODES

    @property
    def is_away_mode_on(self):
        """Return the current away mode status."""
        return self._api.away_mode

    @property
    def current_fan_mode(self):
        """Return the current fan mode."""
        return FAN_MODES[self._api.fan_mode]

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return FAN_MODES

    def set_temperature(self, **kwargs):
        """Set new target temperature. API expects a tuple."""
        if not self._api.away_mode:
            if kwargs.get(ATTR_TEMPERATURE) is not None:
                self._api.set_points = (kwargs.get(ATTR_TEMPERATURE), )
            else:
                self._api.set_points = (kwargs.get(ATTR_TARGET_TEMP_LOW),
                                        kwargs.get(ATTR_TARGET_TEMP_HIGH))

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        if not self._api.away_mode:
            self._api.fan_mode = FAN_MODES.index(fan_mode)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        if not self._api.away_mode:
            self._api.op_mode = OP_MODES.index(operation_mode)

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._api.away_mode = 1

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._api.away_mode = 0
