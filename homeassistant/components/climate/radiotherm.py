"""
Support for Radio Thermostat wifi-enabled home thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.radiotherm/
"""
# pylint: disable=no-member
# pylint: disable=broad-except
import datetime
import json
import logging
import requests
import voluptuous as vol

from homeassistant.components.climate import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, STATE_IDLE, STATE_ON, STATE_OFF,
    ClimateDevice, PRECISION_HALVES, PLATFORM_SCHEMA)
from homeassistant.const import CONF_HOST, TEMP_FAHRENHEIT, ATTR_TEMPERATURE
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['radiotherm==1.3']

_LOGGER = logging.getLogger(__name__)

ATTR_FAN = 'fan'
ATTR_MODE = 'mode'

CONF_HOLD_TEMP = 'hold_temp'
CONF_AWAY_TEMPERATURE_HEAT = 'away_temperature_heat'
CONF_AWAY_TEMPERATURE_COOL = 'away_temperature_cool'

DEFAULT_AWAY_TEMPERATURE_HEAT = 60
DEFAULT_AWAY_TEMPERATURE_COOL = 85

# Mappings from radiotherm json data to HASS state flags.
# Temperature mode of the thermostat.
NAME_TEMP_MODE = {0: STATE_OFF, 1: STATE_HEAT, 2: STATE_COOL, 3: STATE_AUTO}
# Active state (is it heating or cooling?)
NAME_TEMP_STATE = {0: STATE_IDLE, 1: STATE_HEAT, 2: STATE_COOL}
# Fan mode
NAME_FAN_MODE = {0: STATE_AUTO, 1: "circulate", 2: STATE_ON}
# Active fan state 
NAME_FAN_STATE = {0: STATE_OFF, 1: STATE_ON}

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
    hosts = []
    if CONF_HOST in config:
        hosts = config[CONF_HOST]
    else:
        # Only needed for automatic discovery.  Using radiotherm for
        # the regular communication is way too slow.  Testing shows
        # that direct comm is less error prone and has much fewer
        # time outs.
        import radiotherm
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
        tstats.append(RadioThermostat(host, hold_temp, away_temps))

    add_devices(tstats, True)


class RadioThermostat(ClimateDevice):
    """Representation of a Radio Thermostat."""

    def __init__(self, host, hold_temp, away_temps):
        """Initialize the thermostat."""
        self._host = host
        self._time_updated = False
        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = STATE_IDLE
        self._name = None
        self._fmode = None
        self._tmode = None
        self._tstate = None
        self._hold_temp = self.round_temp(hold_temp)
        self._away = False
        self._away_temps = [self.round_temp(i) for i in away_temps]
        self._prev_temp = None
        self._operation_list = [STATE_AUTO, STATE_COOL, STATE_HEAT, STATE_OFF]
        self._fan_list = [STATE_ON, STATE_AUTO]

    @property
    def name(self):
        """Return the name of the Radio Thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_HALVES

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_FAN: self._fmode,
            ATTR_MODE: self._tmode,
        }

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    @property
    def current_fan_mode(self):
        """Return whether the fan is on."""
        return self._fmode

    def set_fan_mode(self, fan):
        """Turn fan on/off."""
        tstat = {}
        if fan == STATE_AUTO or fan == STATE_OFF:
            tstat["fmode"] = 0
        elif fan == STATE_ON:
            tstat["fmode"] = 2

        if tstat:
            self.url_post("tstat", tstat)

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
        """Update and validate the data from the thermostat."""
        # Radio thermostats are very slow, and sometimes don't respond
        # very quickly.  So we need to keep the number of calls to them
        # to a bare minimum or we'll hit the HASS 10 sec warning.  We
        # have to make one call to /tstat to get temps but we'll try and
        # keep the other calls to a minimum.  Even with this, these
        # thermostats tend to time out sometimes when they're actively
        # heating or cooling.

        # Only set the time if the name has been found.  This keeps
        # the number of calls to the thermostat at a max of 2 per
        # update.
        if self._name and not self._time_updated:
            self.set_time()

        # First time - get the name from the thermostat.  This is
        # normally set in the radio thermostat web app.
        if self._name is None:
            data = self.url_get('sys/name')
            if data:
                self._name = data['name']

        # Get the current thermostat state.
        data = self.url_get('tstat')
        if not data:
            return

        # If the thermostat is busy, it may return -1 as the temp in
        # which case it couldn't answer the request.
        elif data['temp'] == -1:
            _LOGGER.warning('%s (%s) was busy (temp == -1)',
                            self._name, self._host)
            return

        self._current_temperature = data['temp']
        self._fmode = NAME_FAN_MODE[data['fmode']]
        self._tmode = NAME_TEMP_MODE[data['tmode']]
        self._tstate = NAME_TEMP_STATE[data['tstate']]

        self._current_operation = self._tmode
        if self._tmode == STATE_COOL:
            self._target_temperature = data['t_cool']
        elif self._tmode == STATE_HEAT:
            self._target_temperature = data['t_heat']
        elif self._tmode == STATE_AUTO:
            if self._tstate == STATE_COOL:
                self._target_temperature = data['t_cool']
            elif self._tstate == STATE_HEAT:
                self._target_temperature = data['t_heat']
        else:
            self._current_operation = STATE_IDLE

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        temperature = self.round_temp(temperature)

        tstat = {}
        if self._current_operation == STATE_COOL:
            tstat['t_cool'] = temperature

        elif self._current_operation == STATE_HEAT:
            tstat['t_heat'] = temperature

        elif self._current_operation == STATE_AUTO:
            if self._tstate == STATE_COOL:
                tstat['t_cool'] = temperature
            elif self._tstate == STATE_HEAT:
                tstat['t_heat'] = temperature

        if self._hold_temp or self._away:
            tstat['hold'] = 1
        else:
            tstat['hold'] = 0

        self.url_post('tstat', tstat)

    def set_time(self):
        """Set device time."""
        now = datetime.datetime.now()
        tstat = {
            'day': now.weekday(),
            'hour': now.hour,
            'minute': now.minute
        }
        if self.url_post('tstat', tstat) is not None:
            self._time_updated = True

    def set_operation_mode(self, operation_mode):
        """Set operation mode (auto, cool, heat, off)."""
        tstat = {}
        if operation_mode == STATE_OFF:
            tstat['tmode'] = 0
        elif operation_mode == STATE_AUTO:
            tstat['tmode'] = 3
        elif operation_mode == STATE_COOL:
            tstat['t_cool'] = self._target_temperature
        elif operation_mode == STATE_HEAT:
            tstat['t_heat'] = self._target_temperature

        self.url_post('tstat', tstat)

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

    def url_get(self, path, timeout=8):
        """Call the thermostat at the input path.

        Return value is the results as a json dictionary or None for an error.
        """
        url = 'http://%s/%s' % (self._host, path)
        try:
            result = requests.get(url, timeout=timeout)
        except Exception:
            _LOGGER.warning('%s (%s) URL %s timed out (%s sec)',
                            self._name, self._host, path, timeout)
            return None

        if result.status_code != requests.codes.ok:
            _LOGGER.warning('%s (%s) URL %s failed with status %s',
                            self._name, self._host, path, result.status_code)
            return None

        return result.json()

    def url_post(self, path, data, timeout=8):
        """Call the thermostat at the input path.

        Return value is the results as a json dictionary or None for an error.
        """
        # The thermostats don't accept regular json data, it must be
        # encoded into a string first.
        url = 'http://%s/%s' % (self._host, path)
        payload = json.dumps(data).encode('UTF-8')
        try:
            result = requests.post(url, data=payload, timeout=timeout)
        except Exception:
            _LOGGER.warning('%s (%s) URL %s timed out (%s sec)',
                            self._name, self._host, path, timeout)
            return None

        if result.status_code != requests.codes.ok:
            _LOGGER.warning('%s (%s) URL %s failed with status %s',
                            self._name, self._host, path, result.status_code)
            return None

        return 0   # OK

    @staticmethod
    def round_temp(temperature):
        """Round a temperature to the resolution of the thermostat.

        RadioThermostats can handle 0.5 degree temps so the input
        temperature is rounded to that value and returned.
        """
        return round(temperature * 2.0) / 2.0
