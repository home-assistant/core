"""
Support for Radio Thermostat wifi-enabled home thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.radiotherm/
"""
import asyncio
import datetime
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    STATE_AUTO, STATE_COOL, STATE_HEAT, STATE_IDLE, STATE_ON, STATE_OFF,
    ClimateDevice, PLATFORM_SCHEMA, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE, SUPPORT_FAN_MODE, SUPPORT_AWAY_MODE)
from homeassistant.const import (
    CONF_HOST, TEMP_FAHRENHEIT, ATTR_TEMPERATURE, PRECISION_HALVES)
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

STATE_CIRCULATE = "circulate"

OPERATION_LIST = [STATE_AUTO, STATE_COOL, STATE_HEAT, STATE_OFF]
CT30_FAN_OPERATION_LIST = [STATE_ON, STATE_AUTO]
CT80_FAN_OPERATION_LIST = [STATE_ON, STATE_CIRCULATE, STATE_AUTO]

# Mappings from radiotherm json data codes to and from HASS state
# flags.  CODE is the thermostat integer code and these map to and
# from HASS state flags.

# Programmed temperature mode of the thermostat.
CODE_TO_TEMP_MODE = {0: STATE_OFF, 1: STATE_HEAT, 2: STATE_COOL, 3: STATE_AUTO}
TEMP_MODE_TO_CODE = {v: k for k, v in CODE_TO_TEMP_MODE.items()}

# Programmed fan mode (circulate is supported by CT80 models)
CODE_TO_FAN_MODE = {0: STATE_AUTO, 1: STATE_CIRCULATE, 2: STATE_ON}
FAN_MODE_TO_CODE = {v: k for k, v in CODE_TO_FAN_MODE.items()}

# Active thermostat state (is it heating or cooling?).  In the future
# this should probably made into heat and cool binary sensors.
CODE_TO_TEMP_STATE = {0: STATE_IDLE, 1: STATE_HEAT, 2: STATE_COOL}

# Active fan state.  This is if the fan is actually on or not.  In the
# future this should probably made into a binary sensor for the fan.
CODE_TO_FAN_STATE = {0: STATE_OFF, 1: STATE_ON}


def round_temp(temperature):
    """Round a temperature to the resolution of the thermostat.

    RadioThermostats can handle 0.5 degree temps so the input
    temperature is rounded to that value and returned.
    """
    return round(temperature * 2.0) / 2.0


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_HOLD_TEMP, default=False): cv.boolean,
    vol.Optional(CONF_AWAY_TEMPERATURE_HEAT,
                 default=DEFAULT_AWAY_TEMPERATURE_HEAT):
    vol.All(vol.Coerce(float), round_temp),
    vol.Optional(CONF_AWAY_TEMPERATURE_COOL,
                 default=DEFAULT_AWAY_TEMPERATURE_COOL):
    vol.All(vol.Coerce(float), round_temp),
})

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                 SUPPORT_FAN_MODE | SUPPORT_AWAY_MODE)


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

    add_devices(tstats, True)


class RadioThermostat(ClimateDevice):
    """Representation of a Radio Thermostat."""

    def __init__(self, device, hold_temp, away_temps):
        """Initialize the thermostat."""
        self.device = device
        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = STATE_IDLE
        self._name = None
        self._fmode = None
        self._fstate = None
        self._tmode = None
        self._tstate = None
        self._hold_temp = hold_temp
        self._hold_set = False
        self._away = False
        self._away_temps = away_temps
        self._prev_temp = None

        # Fan circulate mode is only supported by the CT80 models.
        import radiotherm
        self._is_model_ct80 = isinstance(self.device,
                                         radiotherm.thermostat.CT80)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        # Set the time on the device.  This shouldn't be in the
        # constructor because it's a network call.  We can't put it in
        # update() because calling it will clear any temporary mode or
        # temperature in the thermostat.  So add it as a future job
        # for the event loop to run.
        self.hass.async_add_job(self.set_time)

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
        if self._is_model_ct80:
            return CT80_FAN_OPERATION_LIST
        return CT30_FAN_OPERATION_LIST

    @property
    def current_fan_mode(self):
        """Return whether the fan is on."""
        return self._fmode

    def set_fan_mode(self, fan_mode):
        """Turn fan on/off."""
        code = FAN_MODE_TO_CODE.get(fan_mode, None)
        if code is not None:
            self.device.fmode = code

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
        return OPERATION_LIST

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

        # First time - get the name from the thermostat.  This is
        # normally set in the radio thermostat web app.
        if self._name is None:
            self._name = self.device.name['raw']

        # Request the current state from the thermostat.
        data = self.device.tstat['raw']

        current_temp = data['temp']
        if current_temp == -1:
            _LOGGER.error('%s (%s) was busy (temp == -1)', self._name,
                          self.device.host)
            return

        # Map thermostat values into various STATE_ flags.
        self._current_temperature = current_temp
        self._fmode = CODE_TO_FAN_MODE[data['fmode']]
        self._fstate = CODE_TO_FAN_STATE[data['fstate']]
        self._tmode = CODE_TO_TEMP_MODE[data['tmode']]
        self._tstate = CODE_TO_TEMP_STATE[data['tstate']]

        self._current_operation = self._tmode
        if self._tmode == STATE_COOL:
            self._target_temperature = data['t_cool']
        elif self._tmode == STATE_HEAT:
            self._target_temperature = data['t_heat']
        elif self._tmode == STATE_AUTO:
            # This doesn't really work - tstate is only set if the HVAC is
            # active. If it's idle, we don't know what to do with the target
            # temperature.
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

        temperature = round_temp(temperature)

        if self._current_operation == STATE_COOL:
            self.device.t_cool = temperature
        elif self._current_operation == STATE_HEAT:
            self.device.t_heat = temperature
        elif self._current_operation == STATE_AUTO:
            if self._tstate == STATE_COOL:
                self.device.t_cool = temperature
            elif self._tstate == STATE_HEAT:
                self.device.t_heat = temperature

        # Only change the hold if requested or if hold mode was turned
        # on and we haven't set it yet.
        if kwargs.get('hold_changed', False) or not self._hold_set:
            if self._hold_temp or self._away:
                self.device.hold = 1
                self._hold_set = True
            else:
                self.device.hold = 0

    def set_time(self):
        """Set device time."""
        # Calling this clears any local temperature override and
        # reverts to the scheduled temperature.
        now = datetime.datetime.now()
        self.device.time = {
            'day': now.weekday(),
            'hour': now.hour,
            'minute': now.minute
        }

    def set_operation_mode(self, operation_mode):
        """Set operation mode (auto, cool, heat, off)."""
        if operation_mode == STATE_OFF or operation_mode == STATE_AUTO:
            self.device.tmode = TEMP_MODE_TO_CODE[operation_mode]

        # Setting t_cool or t_heat automatically changes tmode.
        elif operation_mode == STATE_COOL:
            self.device.t_cool = self._target_temperature
        elif operation_mode == STATE_HEAT:
            self.device.t_heat = self._target_temperature

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
        self.set_temperature(temperature=away_temp, hold_changed=True)

    def turn_away_mode_off(self):
        """Turn away off."""
        self._away = False
        self.set_temperature(temperature=self._prev_temp, hold_changed=True)
