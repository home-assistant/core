"""
Support for IntesisHome Smart AC Controllers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.intesishome/
"""

import logging
from datetime import timedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME, CONF_STRUCTURE)
from homeassistant.util import Throttle
from homeassistant.components import persistent_notification
from homeassistant.components.climate import (ClimateDevice,
                                              PLATFORM_SCHEMA,
                                              ATTR_TEMPERATURE,
                                              ATTR_OPERATION_MODE)
from homeassistant.const import (TEMP_CELSIUS, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'IntesisHome'
REQUIREMENTS = ['pyintesishome==0.4']
STATE_FAN = 'Fan'
STATE_HEAT = 'Heat'
STATE_COOL = 'Cool'
STATE_DRY = 'Dry'
STATE_AUTO = 'Auto'
STATE_QUIET = 'Quiet'
STATE_LOW = 'Low'
STATE_MEDIUM = 'Medium'
STATE_HIGH = 'High'
STATE_OFF = 'Off'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_STRUCTURE): vol.All(cv.ensure_list, cv.string),
})

# Return cached results if last scan time was less than this value.
# If a persistent connection is established for the controller,
# changes to values are in realtime.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)

try:
    # pylint: disable=unused-import
    from asyncio import ensure_future
except ImportError:
    # Python 3.4.3 and ealier has this as async
    # pylint: disable=unused-import
    from asyncio import async
    ensure_future = async


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the IntesisHome interface."""
    from pyintesishome import IntesisHome

    _user = config.get(CONF_USERNAME)
    _pass = config.get(CONF_PASSWORD)

    if 'climate_intesishome' not in hass.data:
        hass.data['climate_intesishome'] = IntesisHome(_user, _pass, hass.loop)

    intesishome = hass.data['climate_intesishome']
    intesishome.connect()

    if intesishome.error_message:
        persistent_notification.create(hass, intesishome.error_message,
                                       "IntesisHome Error", 'intesishome')
    add_devices([IntesisAC(deviceid, device, hass)
                 for deviceid, device in intesishome.get_devices().items()])
    return True


class IntesisAC(ClimateDevice):
    """Representation of an IntesisHome thermostat."""

    def __init__(self, deviceid, device, hass):
        """Initialize the thermostat."""
        _LOGGER.debug('Added climate device with state: %s', repr(device))
        self._intesishome = hass.data.get('climate_intesishome')

        self._deviceid = deviceid
        self._devicename = device['name']

        self._max_temp = None
        self._min_temp = None
        self._target_temp = None
        self._current_temp = None
        self._run_hours = None
        self._rssi = None
        self._swing = None
        self._has_swing_control = False

        self._power = STATE_UNKNOWN
        self._fan_speed = STATE_UNKNOWN
        self._current_operation = STATE_UNKNOWN

        self._operation_list = [STATE_AUTO, STATE_COOL, STATE_HEAT, STATE_DRY,
                                STATE_FAN, STATE_OFF]
        self._fan_list = [STATE_AUTO, STATE_QUIET, STATE_LOW, STATE_MEDIUM,
                          STATE_HIGH]
        self._swing_list = ["Auto/Stop", "Swing", "Middle"]

        # Best guess as which widget represents vertical swing control
        if 42 in device.get('widgets'):
            self._has_swing_control = True

        self._intesishome.add_update_callback(self.update_callback)
        self.update()

    @property
    def name(self):
        """Return the name of the AC device."""
        return self._devicename

    @property
    def temperature_unit(self):
        """Return the unit of measurement of the platform."""
        return TEMP_CELSIUS

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        if self._intesishome.is_connected:
            update_type = 'Push'
        else:
            update_type = 'Poll'

        return {
            "run_hours": self._run_hours,
            "rssi": self._rssi,
            "temperature": self._target_temp,
            "ha_update_type": update_type,
        }

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        _LOGGER.debug("Set Temperature=%s")

        temperature = kwargs.get(ATTR_TEMPERATURE)
        operation_mode = kwargs.get(ATTR_OPERATION_MODE)

        if operation_mode:
            self._target_temp = temperature
            self.set_operation_mode(operation_mode)
        else:
            if temperature:
                self._intesishome.set_temperature(self._deviceid, temperature)

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        _LOGGER.debug("Set Mode=%s", operation_mode)
        if operation_mode == STATE_OFF:
            self._intesishome.set_power_off(self._deviceid)
        else:
            if self._intesishome.get_power_state(self._deviceid) == 'off':
                self._intesishome.set_power_on(self._deviceid)

            if operation_mode == STATE_HEAT:
                self._intesishome.set_mode_heat(self._deviceid)
            elif operation_mode == STATE_COOL:
                self._intesishome.set_mode_cool(self._deviceid)
            elif operation_mode == STATE_AUTO:
                self._intesishome.set_mode_auto(self._deviceid)
            elif operation_mode == STATE_FAN:
                self._intesishome.set_mode_fan(self._deviceid)
                self._target_temp = None
            elif operation_mode == STATE_DRY:
                self._intesishome.set_mode_dry(self._deviceid)

            if self._target_temp:
                self._intesishome.set_temperature(self._deviceid,
                                                  self._target_temp)

    def set_fan_mode(self, fan):
        """Set fan mode (from quiet, low, medium, high, auto)."""
        self._intesishome.set_fan_speed(self._deviceid, fan.lower())

    def set_swing_mode(self, swing):
        """Set the vertical vane."""
        if swing == "Auto/Stop":
            self._intesishome.set_vertical_vane(self._deviceid, 'auto/stop')
            self._intesishome.set_horizontal_vane(self._deviceid, 'auto/stop')
        elif swing == "Swing":
            self._intesishome.set_vertical_vane(self._deviceid, 'swing')
            self._intesishome.set_horizontal_vane(self._deviceid, 'swing')
        elif swing == "Middle":
            self._intesishome.set_vertical_vane(self._deviceid, 'manual3')
            self._intesishome.set_horizontal_vane(self._deviceid, 'swing')

    def update(self):
        """Update Home Assistant state from pyIntesisHome."""
        if self._intesishome.is_disconnected:
            self._poll_status(False)

        self._current_temp = self._intesishome.get_temperature(self._deviceid)
        self._min_temp = self._intesishome.get_min_setpoint(self._deviceid)
        self._max_temp = self._intesishome.get_max_setpoint(self._deviceid)
        self._rssi = self._intesishome.get_rssi(self._deviceid)
        self._run_hours = self._intesishome.get_run_hours(self._deviceid)

        # Operation mode
        mode = self._intesishome.get_mode(self._deviceid)
        if self._intesishome.get_power_state(self._deviceid) == 'off':
            self._current_operation = STATE_OFF
            self._fan_speed = None
            self._swing = None
        elif mode == 'auto':
            self._current_operation = STATE_AUTO
        elif mode == 'fan':
            self._current_operation = STATE_FAN
        elif mode == 'heat':
            self._current_operation = STATE_HEAT
        elif mode == 'dry':
            self._current_operation = STATE_DRY
        elif mode == 'cool':
            self._current_operation = STATE_COOL
        else:
            self._current_operation = STATE_UNKNOWN

        # Target temperature
        if self._current_operation in [STATE_OFF, STATE_FAN]:
            self._target_temp = None
        else:
            self._target_temp = self._intesishome.get_setpoint(self._deviceid)

        # Fan speed
        fan_speed = self._intesishome.get_fan_speed(self._deviceid)
        if fan_speed:
            # Capitalize fan speed from pyintesishome
            self._fan_speed = fan_speed[:1].upper() + fan_speed[1:]

        # Swing mode
        # Climate module only supports one swing setting, so use vertical swing
        swing = self._intesishome.get_vertical_swing(self._deviceid)
        if not self._has_swing_control:
            # Device doesn't support swing
            self._swing = None
        elif swing == 'auto/stop':
            self._swing = "Auto/Stop"
        elif swing == 'swing':
            self._swing = "Swing"
        elif swing == 'manual3':
            self._swing = "Middle"
        else:
            self._swing = STATE_UNKNOWN

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _poll_status(self, shouldcallback):
        """Internal method to poll IntesisHome via HTTP."""
        _LOGGER.debug("Polling IntesisHome Status via HTTP")
        self._intesishome.poll_status(shouldcallback)

    @property
    def icon(self):
        """Set the climate icon to the approprate function."""
        icon = None
        if self._current_operation == STATE_HEAT:
            icon = 'mdi:white-balance-sunny'
        elif self._current_operation == STATE_FAN:
            icon = 'mdi:fan'
        elif self._current_operation == STATE_DRY:
            icon = 'mdi:water-off'
        elif self._current_operation == STATE_COOL:
            icon = 'mdi:nest-thermostat'
        elif self._current_operation == STATE_AUTO:
            icon = 'mdi:cached'
        return icon

    def update_callback(self):
        """Called when data is received by pyIntesishome."""
        _LOGGER.debug("IntesisHome sent a status update.")
        self.hass.async_add_job(self.update_ha_state, True)

    @property
    def min_temp(self):
        """Return the minimum temperature from the IntesisHome interface."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature from the IntesisHome interface."""
        return self._max_temp

    @property
    def should_poll(self):
        """Poll for updates if pyIntesisHome doesn't have a socket open."""
        if self._intesishome.is_connected:
            return False
        else:
            return True

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    @property
    def current_fan_mode(self):
        """Return whether the fan is on."""
        return self._fan_speed

    @property
    def current_swing_mode(self):
        """Return current swing mode."""
        return self._swing

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    @property
    def swing_list(self):
        """List of available swing positions."""
        return self._swing_list

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def current_operation(self):
        """Return the current operation mode."""
        return self._current_operation

    @property
    def target_temperature(self):
        """Return the current setpoint temperature."""
        return self._target_temp

    @property
    def target_temperature_low(self):
        """Not implemented."""
        return None

    @property
    def target_temperature_high(self):
        """Not implemented."""
        return None

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return None
