"""Support for Radio Thermostat wifi-enabled home thermostats."""
import logging

import radiotherm
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_OFF,
    FAN_ON,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_HOME,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    PRECISION_HALVES,
    STATE_ON,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_FAN_ACTION = "fan_action"

CONF_HOLD_TEMP = "hold_temp"

PRESET_HOLIDAY = "holiday"

PRESET_ALTERNATE = "alternate"

STATE_CIRCULATE = "circulate"

PRESET_MODES = [PRESET_HOME, PRESET_ALTERNATE, PRESET_AWAY, PRESET_HOLIDAY]

OPERATION_LIST = [HVAC_MODE_AUTO, HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_OFF]
CT30_FAN_OPERATION_LIST = [STATE_ON, HVAC_MODE_AUTO]
CT80_FAN_OPERATION_LIST = [STATE_ON, STATE_CIRCULATE, HVAC_MODE_AUTO]

# Mappings from radiotherm json data codes to and from Home Assistant state
# flags.  CODE is the thermostat integer code and these map to and
# from Home Assistant state flags.

# Programmed temperature mode of the thermostat.
CODE_TO_TEMP_MODE = {
    0: HVAC_MODE_OFF,
    1: HVAC_MODE_HEAT,
    2: HVAC_MODE_COOL,
    3: HVAC_MODE_AUTO,
}
TEMP_MODE_TO_CODE = {v: k for k, v in CODE_TO_TEMP_MODE.items()}

# Programmed fan mode (circulate is supported by CT80 models)
CODE_TO_FAN_MODE = {0: HVAC_MODE_AUTO, 1: STATE_CIRCULATE, 2: STATE_ON}

FAN_MODE_TO_CODE = {v: k for k, v in CODE_TO_FAN_MODE.items()}

# Active thermostat state (is it heating or cooling?).  In the future
# this should probably made into heat and cool binary sensors.
CODE_TO_TEMP_STATE = {0: CURRENT_HVAC_IDLE, 1: CURRENT_HVAC_HEAT, 2: CURRENT_HVAC_COOL}

# Active fan state.  This is if the fan is actually on or not.  In the
# future this should probably made into a binary sensor for the fan.
CODE_TO_FAN_STATE = {0: FAN_OFF, 1: FAN_ON}

PRESET_MODE_TO_CODE = {"home": 0, "alternate": 1, "away": 2, "holiday": 3}

CODE_TO_PRESET_MODE = {0: "home", 1: "alternate", 2: "away", 3: "holiday"}


def round_temp(temperature):
    """Round a temperature to the resolution of the thermostat.

    RadioThermostats can handle 0.5 degree temps so the input
    temperature is rounded to that value and returned.
    """
    return round(temperature * 2.0) / 2.0


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_HOLD_TEMP, default=False): cv.boolean,
    }
)


SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Radio Thermostat."""
    hosts = []
    if CONF_HOST in config:
        hosts = config[CONF_HOST]
    else:
        hosts.append(radiotherm.discover.discover_address())

    if hosts is None:
        _LOGGER.error("No Radiotherm Thermostats detected")
        return False

    hold_temp = config.get(CONF_HOLD_TEMP)
    tstats = []

    for host in hosts:
        try:
            tstat = radiotherm.get_thermostat(host)
            tstats.append(RadioThermostat(tstat, hold_temp))
        except OSError:
            _LOGGER.exception("Unable to connect to Radio Thermostat: %s", host)

    add_entities(tstats, True)


class RadioThermostat(ClimateDevice):
    """Representation of a Radio Thermostat."""

    def __init__(self, device, hold_temp):
        """Initialize the thermostat."""
        self.device = device
        self._target_temperature = None
        self._current_temperature = None
        self._current_humidity = None
        self._current_operation = HVAC_MODE_OFF
        self._name = None
        self._fmode = None
        self._fstate = None
        self._tmode = None
        self._tstate = None
        self._hold_temp = hold_temp
        self._hold_set = False
        self._prev_temp = None
        self._preset_mode = None
        self._program_mode = None
        self._is_away = False

        # Fan circulate mode is only supported by the CT80 models.
        self._is_model_ct80 = isinstance(self.device, radiotherm.thermostat.CT80)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    async def async_added_to_hass(self):
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
        return {ATTR_FAN_ACTION: self._fstate}

    @property
    def fan_modes(self):
        """List of available fan modes."""
        if self._is_model_ct80:
            return CT80_FAN_OPERATION_LIST
        return CT30_FAN_OPERATION_LIST

    @property
    def fan_mode(self):
        """Return whether the fan is on."""
        return self._fmode

    def set_fan_mode(self, fan_mode):
        """Turn fan on/off."""
        code = FAN_MODE_TO_CODE.get(fan_mode)
        if code is not None:
            self.device.fmode = code

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def current_humidity(self):
        """Return the current temperature."""
        return self._current_humidity

    @property
    def hvac_mode(self):
        """Return the current operation. head, cool idle."""
        return self._current_operation

    @property
    def hvac_modes(self):
        """Return the operation modes list."""
        return OPERATION_LIST

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported."""
        if self.hvac_mode == HVAC_MODE_OFF:
            return None
        return self._tstate

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self._program_mode == 0:
            return PRESET_HOME
        if self._program_mode == 1:
            return PRESET_ALTERNATE
        if self._program_mode == 2:
            return PRESET_AWAY
        if self._program_mode == 3:
            return PRESET_HOLIDAY

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return PRESET_MODES

    def update(self):
        """Update and validate the data from the thermostat."""
        # Radio thermostats are very slow, and sometimes don't respond
        # very quickly.  So we need to keep the number of calls to them
        # to a bare minimum or we'll hit the Home Assistant 10 sec warning.  We
        # have to make one call to /tstat to get temps but we'll try and
        # keep the other calls to a minimum.  Even with this, these
        # thermostats tend to time out sometimes when they're actively
        # heating or cooling.

        # First time - get the name from the thermostat.  This is
        # normally set in the radio thermostat web app.
        if self._name is None:
            self._name = self.device.name["raw"]

        # Request the current state from the thermostat.
        try:
            data = self.device.tstat["raw"]
        except radiotherm.validate.RadiothermTstatError:
            _LOGGER.warning(
                "%s (%s) was busy (invalid value returned)",
                self._name,
                self.device.host,
            )
            return

        current_temp = data["temp"]

        if self._is_model_ct80:
            try:
                humiditydata = self.device.humidity["raw"]
            except radiotherm.validate.RadiothermTstatError:
                _LOGGER.warning(
                    "%s (%s) was busy (invalid value returned)",
                    self._name,
                    self.device.host,
                )
                return
            self._current_humidity = humiditydata
            self._program_mode = data["program_mode"]
            self._preset_mode = CODE_TO_PRESET_MODE[data["program_mode"]]

        # Map thermostat values into various STATE_ flags.
        self._current_temperature = current_temp
        self._fmode = CODE_TO_FAN_MODE[data["fmode"]]
        self._fstate = CODE_TO_FAN_STATE[data["fstate"]]
        self._tmode = CODE_TO_TEMP_MODE[data["tmode"]]
        self._tstate = CODE_TO_TEMP_STATE[data["tstate"]]

        self._current_operation = self._tmode
        if self._tmode == HVAC_MODE_COOL:
            self._target_temperature = data["t_cool"]
        elif self._tmode == HVAC_MODE_HEAT:
            self._target_temperature = data["t_heat"]
        elif self._tmode == HVAC_MODE_AUTO:
            # This doesn't really work - tstate is only set if the HVAC is
            # active. If it's idle, we don't know what to do with the target
            # temperature.
            if self._tstate == CURRENT_HVAC_COOL:
                self._target_temperature = data["t_cool"]
            elif self._tstate == CURRENT_HVAC_HEAT:
                self._target_temperature = data["t_heat"]
        else:
            self._current_operation = HVAC_MODE_OFF

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        temperature = round_temp(temperature)

        if self._current_operation == HVAC_MODE_COOL:
            self.device.t_cool = temperature
        elif self._current_operation == HVAC_MODE_HEAT:
            self.device.t_heat = temperature
        elif self._current_operation == HVAC_MODE_AUTO:
            if self._tstate == CURRENT_HVAC_COOL:
                self.device.t_cool = temperature
            elif self._tstate == CURRENT_HVAC_HEAT:
                self.device.t_heat = temperature

        # Only change the hold if requested or if hold mode was turned
        # on and we haven't set it yet.
        if kwargs.get("hold_changed", False) or not self._hold_set:
            if self._hold_temp:
                self.device.hold = 1
                self._hold_set = True
            else:
                self.device.hold = 0

    def set_time(self):
        """Set device time."""
        # Calling this clears any local temperature override and
        # reverts to the scheduled temperature.
        now = dt_util.now()
        self.device.time = {
            "day": now.weekday(),
            "hour": now.hour,
            "minute": now.minute,
        }

    def set_hvac_mode(self, hvac_mode):
        """Set operation mode (auto, cool, heat, off)."""
        if hvac_mode in (HVAC_MODE_OFF, HVAC_MODE_AUTO):
            self.device.tmode = TEMP_MODE_TO_CODE[hvac_mode]

        # Setting t_cool or t_heat automatically changes tmode.
        elif hvac_mode == HVAC_MODE_COOL:
            self.device.t_cool = self._target_temperature
        elif hvac_mode == HVAC_MODE_HEAT:
            self.device.t_heat = self._target_temperature

    def set_preset_mode(self, preset_mode):
        """Set Preset mode (Home, Alternate, Away, Holiday)."""
        if preset_mode in (PRESET_MODES):
            self.device.program_mode = PRESET_MODE_TO_CODE[preset_mode]
        else:
            _LOGGER.error(
                "preset_mode  %s not in PRESET_MODES", preset_mode,
            )
