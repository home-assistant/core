"""
Support for Wi-Fi enabled iRobot Roombas.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.roomba/
"""
import asyncio
import logging

import async_timeout
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.vacuum import (
    PLATFORM_SCHEMA, STATE_CLEANING, STATE_DOCKED, STATE_ERROR, STATE_IDLE,
    STATE_PAUSED, STATE_RETURNING, SUPPORT_BATTERY, SUPPORT_FAN_SPEED,
    SUPPORT_PAUSE, SUPPORT_RETURN_HOME, SUPPORT_SEND_COMMAND, SUPPORT_STATE,
    SUPPORT_STOP, StateVacuumDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.exceptions import PlatformNotReady

REQUIREMENTS = ['roombapy==1.3.1']

_LOGGER = logging.getLogger(__name__)

ATTR_BIN_FULL = 'bin_full'
ATTR_BIN_PRESENT = 'bin_present'
ATTR_CLEANING_TIME = 'cleaning_time'
ATTR_CLEANED_AREA = 'cleaned_area'
ATTR_ERROR = 'error'
ATTR_POSITION = 'position'
ATTR_SOFTWARE_VERSION = 'software_version'

CAP_BIN_FULL = 'bin_full'
CAP_POSITION = 'position'
CAP_CARPET_BOOST = 'carpet_boost'

CONF_CERT = 'certificate'
CONF_CONTINUOUS = 'continuous'

DEFAULT_CERT = '/etc/ssl/certs/ca-certificates.crt'
DEFAULT_CONTINUOUS = True
DEFAULT_NAME = 'Roomba'

PLATFORM = 'roomba'

FAN_SPEED_AUTOMATIC = 'Automatic'
FAN_SPEED_ECO = 'Eco'
FAN_SPEED_PERFORMANCE = 'Performance'
FAN_SPEEDS = [FAN_SPEED_AUTOMATIC, FAN_SPEED_ECO, FAN_SPEED_PERFORMANCE]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_CERT, default=DEFAULT_CERT): cv.string,
    vol.Optional(CONF_CONTINUOUS, default=DEFAULT_CONTINUOUS): cv.boolean,
}, extra=vol.ALLOW_EXTRA)

# Commonly supported features
SUPPORT_ROOMBA = SUPPORT_BATTERY | SUPPORT_PAUSE | SUPPORT_RETURN_HOME | \
    SUPPORT_SEND_COMMAND | SUPPORT_STATE | SUPPORT_STOP

# Only Roombas with CarpetBost can set their fanspeed
SUPPORT_ROOMBA_CARPET_BOOST = SUPPORT_ROOMBA | SUPPORT_FAN_SPEED

STATUS_TO_STATE = {
    'Charging': STATE_DOCKED,
    'New Mission': STATE_CLEANING,
    'Running': STATE_CLEANING,
    'Recharging': STATE_DOCKED,
    'Stuck': STATE_ERROR,
    'User Docking': STATE_RETURNING,
    'Docking': STATE_RETURNING,
    'Docking - End Mission': STATE_RETURNING,
    'Cancelled': STATE_RETURNING,
    'Stopped': STATE_IDLE,
    'Paused': STATE_PAUSED,
    'End Mission': STATE_DOCKED,
}


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):  # noqa:E501
    """Set up the iRobot Roomba vacuum cleaner platform."""
    from roomba import Roomba
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    certificate = config.get(CONF_CERT)
    continuous = config.get(CONF_CONTINUOUS)

    # Create handler
    roomba = Roomba(
        address=host,
        blid=username,
        password=password,
        cert_name=certificate,
        continuous=continuous
    )
    _LOGGER.info("Initializing communication with host %s (username: %s)",
                 host, username)

    try:
        with async_timeout.timeout(9):
            await hass.async_add_job(roomba.connect)
    except asyncio.TimeoutError:
        raise PlatformNotReady

    roomba_vac = RoombaVacuum(name, roomba)
    hass.data[PLATFORM][host] = roomba_vac

    async_add_devices([roomba_vac], update_before_add=True)


class RoombaVacuum(StateVacuumDevice):
    """Representation of a Roomba Vacuum cleaner robot."""

    def __init__(self, name, roomba):
        """Initialize the Roomba handler."""
        self._available = False
        self._battery_level = None
        self._capabilities = {}
        self._fan_speed = None
        self._name = name
        self._state = None
        self._state_attrs = {}
        self.vacuum = roomba
        self.vacuum_state = None

    @property
    def state(self):
        """Return the state of the vacuum cleaner."""
        return self._state

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        if self._capabilities.get(CAP_CARPET_BOOST):
            return SUPPORT_ROOMBA_CARPET_BOOST
        return SUPPORT_ROOMBA

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self._fan_speed

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        if not self._capabilities.get(CAP_CARPET_BOOST):
            return None
        return FAN_SPEEDS

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    def start(self, **kwargs):
        """Start a cleaning cycle."""
        self.send_command('start')

    def stop(self, **kwargs):
        """Stop a cleaning cycle and return to base."""
        self.send_command('stop')

    def resume(self, **kwargs):
        """Resume the cleaning cycle."""
        self.send_command('resume')

    def pause(self, **kwargs):
        """Pause the cleaning cycle."""
        self.send_command('pause')

    def start_pause(self, **kwargs):
        """Pause the cleaning task or resume it."""
        if self.state == STATE_CLEANING:  # vacuum is running
            self.pause()
        elif self.state == STATE_PAUSED:  # vacuum is stopped
            self.resume()
        else:  # vacuum is off
            self.start()

    def return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        self.vacuum.send_command('dock')

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if fan_speed.capitalize() in FAN_SPEEDS:
            fan_speed = fan_speed.capitalize()
        _LOGGER.debug("Set fan speed to: %s", fan_speed)
        high_perf = None
        carpet_boost = None
        if fan_speed == FAN_SPEED_AUTOMATIC:
            high_perf = False
            carpet_boost = True
            self._fan_speed = FAN_SPEED_AUTOMATIC
        elif fan_speed == FAN_SPEED_ECO:
            high_perf = False
            carpet_boost = False
            self._fan_speed = FAN_SPEED_ECO
        elif fan_speed == FAN_SPEED_PERFORMANCE:
            high_perf = True
            carpet_boost = False
            self._fan_speed = FAN_SPEED_PERFORMANCE
        else:
            _LOGGER.error("No such fan speed available: %s", fan_speed)
            return
        # The set_preference method does only accept string values
        self.vacuum.set_preference('carpetBoost', str(carpet_boost))
        self.vacuum.set_preference('vacHigh', str(high_perf))

    def send_command(self, command, params=None, **kwargs):
        """Send raw command."""
        self.vacuum.send_command(command)

    async def async_update(self):
        """Fetch state from the device."""
        # No data, no update
        if not self.vacuum.master_state:
            _LOGGER.debug("Roomba %s has no data yet. Skip update.",
                          self.name)
            return
        state = self.vacuum.master_state.get('state', {}).get('reported', {})
        _LOGGER.debug("Got new state from the vacuum: %s", state)
        self.vacuum_state = state
        self._available = True

        # Roomba software version
        software_version = state.get('softwareVer')

        # Get the capabilities of our unit
        capabilities = state.get('cap', {})
        cap_bin_full = capabilities.get('binFullDetect')
        cap_carpet_boost = capabilities.get('carpetBoost')
        cap_pos = capabilities.get('pose')
        # Store capabilities
        self._capabilities = {
            CAP_BIN_FULL:  cap_bin_full == 1,
            CAP_CARPET_BOOST: cap_carpet_boost == 1,
            CAP_POSITION: cap_pos == 1,
        }
        self._battery_level = state.get('batPct')

        bin_state = state.get('bin', {})

        # Vacuum state
        try:
            if self.vacuum.current_state is not None:
                self._state = STATUS_TO_STATE[self.vacuum.current_state]
            else:
                self._state = None
        except KeyError:
            _LOGGER.error("Status not supported: %s",
                          self.vacuum.current_state)

        # Error message in plain english
        # Skip error attr if there is none
        if hasattr(self.vacuum, 'error_message'):
            self._state_attrs[ATTR_ERROR] = self.vacuum.error_message

        # Set properties that are to appear in the GUI
        self._state_attrs = {
            ATTR_BIN_PRESENT: bin_state.get('present'),
            ATTR_SOFTWARE_VERSION: software_version
        }

        # Only add cleaning time and cleaned area attrs when the vacuum is
        # currently on
        if self._state == STATE_CLEANING:
            # Get clean mission status
            mission_state = state.get('cleanMissionStatus', {})
            cleaning_time = mission_state.get('mssnM')
            cleaned_area = mission_state.get('sqft')  # Imperial
            # Convert to m2 if the unit_system is set to metric
            if cleaned_area and self.hass.config.units.is_metric:
                cleaned_area = round(cleaned_area * 0.0929)
            self._state_attrs[ATTR_CLEANING_TIME] = cleaning_time
            self._state_attrs[ATTR_CLEANED_AREA] = cleaned_area

        # Not all Roombas expose position data
        # https://github.com/koalazak/dorita980/issues/48
        if self._capabilities[CAP_POSITION]:
            pos_state = state.get('pose', {})
            position = None
            pos_x = pos_state.get('point', {}).get('x')
            pos_y = pos_state.get('point', {}).get('y')
            theta = pos_state.get('theta')
            if all(item is not None for item in [pos_x, pos_y, theta]):
                position = '({}, {}, {})'.format(pos_x, pos_y, theta)
            self._state_attrs[ATTR_POSITION] = position

        # Not all Roombas have a bin full sensor
        if self._capabilities[CAP_BIN_FULL]:
            self._state_attrs[ATTR_BIN_FULL] = bin_state.get('full')

        # Fan speed mode (Performance, Automatic or Eco)
        # Not all Roombas expose carpet boost
        if self._capabilities[CAP_CARPET_BOOST]:
            fan_speed = None
            carpet_boost = state.get('carpetBoost')
            high_perf = state.get('vacHigh')

            if carpet_boost is not None and high_perf is not None:
                if carpet_boost:
                    fan_speed = FAN_SPEED_AUTOMATIC
                elif high_perf:
                    fan_speed = FAN_SPEED_PERFORMANCE
                else:  # carpet_boost and high_perf are False
                    fan_speed = FAN_SPEED_ECO

            self._fan_speed = fan_speed
