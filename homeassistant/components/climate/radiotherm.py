"""
Support for Radio Thermostat wifi-enabled home thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.radiotherm/
"""
import datetime
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, STATE_IDLE, STATE_OFF,
    ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_HOST, TEMP_FAHRENHEIT, ATTR_TEMPERATURE
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['radiotherm==1.2']

_LOGGER = logging.getLogger(__name__)

ATTR_FAN = 'fan'
ATTR_MODE = 'mode'

CONF_HOLD_TEMP = 'hold_temp'
CONF_AWAY_TEMPERATURE_HEAT = 'away_temperature_heat'
CONF_AWAY_TEMPERATURE_COOL = 'away_temperature_cool'

DEFAULT_AWAY_TEMPERATURE_HEAT = 60
DEFAULT_AWAY_TEMPERATURE_COOL = 85

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_HOLD_TEMP, default=False): cv.boolean,
    vol.Optional(CONF_AWAY_TEMPERATURE_HEAT,
                 default=DEFAULT_AWAY_TEMPERATURE_HEAT): vol.Coerce(float),
    vol.Optional(CONF_AWAY_TEMPERATURE_COOL,
                 default=DEFAULT_AWAY_TEMPERATURE_COOL): vol.Coerce(float),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Radio Thermostat."""
    import radiotherm

    hosts = []
    if CONF_HOST in config:
        hosts = config[CONF_HOST]
    else:
        hosts.append(radiotherm.discover.discover_address())

    if hosts is None:
        _LOGGER.error("No Radiotherm Thermostats detected")
        return False

    hold_temp = config.get(CONF_HOLD_TEMP)
    away_temps = [
        config.get(CONF_AWAY_TEMPERATURE_HEAT),
        config.get(CONF_AWAY_TEMPERATURE_COOL)
    ]
    tstats = []

    for host in hosts:
        try:
            tstat = radiotherm.get_thermostat(host)
            tstats.append(RadioThermostat(tstat, hold_temp, away_temps))
        except OSError:
            _LOGGER.exception("Unable to connect to Radio Thermostat: %s",
                              host)

    add_devices(tstats)


class RadioThermostat(ClimateDevice):
    """Representation of a Radio Thermostat."""

    def __init__(self, device, hold_temp, away_temps):
        """Initialize the thermostat."""
        self.device = device
        self.set_time()
        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = STATE_IDLE
        self._name = None
        self._fmode = None
        self._tmode = None
        self._hold_temp = hold_temp
        self._away = False
        self._away_temps = away_temps
        self._prev_temp = None
        self.update()
        self._operation_list = [STATE_AUTO, STATE_COOL, STATE_HEAT, STATE_OFF]

    @property
    def name(self):
        """Return the name of the Radio Thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_FAN: self._fmode,
            ATTR_MODE: self._tmode,
        }

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def current_operation(self):
        """Return the current operation. head, cool idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the operation modes list."""
        return self._operation_list

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._away

    def update(self):
        """Update the data from the thermostat."""
        self._current_temperature = self.device.temp['raw']
        self._name = self.device.name['raw']
        self._fmode = self.device.fmode['human']
        self._tmode = self.device.tmode['human']

        if self._tmode == 'Cool':
            self._target_temperature = self.device.t_cool['raw']
            self._current_operation = STATE_COOL
        elif self._tmode == 'Heat':
            self._target_temperature = self.device.t_heat['raw']
            self._current_operation = STATE_HEAT
        else:
            self._current_operation = STATE_IDLE

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        if self._current_operation == STATE_COOL:
            self.device.t_cool = round(temperature * 2.0) / 2.0
        elif self._current_operation == STATE_HEAT:
            self.device.t_heat = round(temperature * 2.0) / 2.0
        if self._hold_temp or self._away:
            self.device.hold = 1
        else:
            self.device.hold = 0

    def set_time(self):
        """Set device time."""
        now = datetime.datetime.now()
        self.device.time = {
            'day': now.weekday(),
            'hour': now.hour,
            'minute': now.minute
        }

    def set_operation_mode(self, operation_mode):
        """Set operation mode (auto, cool, heat, off)."""
        if operation_mode == STATE_OFF:
            self.device.tmode = 0
        elif operation_mode == STATE_AUTO:
            self.device.tmode = 3
        elif operation_mode == STATE_COOL:
            self.device.t_cool = round(self._target_temperature * 2.0) / 2.0
        elif operation_mode == STATE_HEAT:
            self.device.t_heat = round(self._target_temperature * 2.0) / 2.0

    def turn_away_mode_on(self):
        """Turn away on.

        The RTCOA app simulates away mode by using a hold.
        """
        away_temp = None
        if not self._away:
            self._prev_temp = self._target_temperature
            if self._current_operation == STATE_HEAT:
                away_temp = self._away_temps[0]
            elif self._current_operation == STATE_COOL:
                away_temp = self._away_temps[1]
        self._away = True
        self.set_temperature(temperature=away_temp)

    def turn_away_mode_off(self):
        """Turn away off."""
        self._away = False
        self.set_temperature(temperature=self._prev_temp)
