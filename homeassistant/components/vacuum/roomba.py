"""
Support for Wi-Fi enabled iRobot Roombas.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.roomba/
"""
from functools import partial
import asyncio
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.vacuum import (
    VacuumDevice,
    PLATFORM_SCHEMA, SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_PAUSE,
    SUPPORT_STOP, SUPPORT_RETURN_HOME, SUPPORT_BATTERY, SUPPORT_STATUS,
    SUPPORT_SEND_COMMAND)
from homeassistant.const import (
    STATE_ON, STATE_OFF, CONF_NAME, CONF_HOST, CONF_USERNAME, CONF_PASSWORD)

REQUIREMENTS = ['https://github.com/pschmitt/Roomba980-Python/archive/'
                '1.2.1.zip'
                '#Roomba980-Python==1.2.1']

_LOGGER = logging.getLogger(__name__)

ATTR_BIN_FULL = 'bin_full'
ATTR_BIN_PRESENT = 'bin_present'
ATTR_CLEANING_TIME = 'cleaning_time'
ATTR_CLEANED_AREA = 'cleaned_area'
ATTR_ERROR = 'error'
ATTR_POSITION = 'position'
ATTR_SOFTWARE_VERSION = 'software_version'

CONF_CERT = 'certificate'
CONF_CONTINUOUS = 'continuous'

DEFAULT_CERT = '/etc/ssl/certs/ca-certificates.crt'
DEFAULT_CONTINUOUS = True
DEFAULT_NAME = 'Roomba'

ICON = 'mdi:roomba'
PLATFORM = 'roomba'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_CERT, default=DEFAULT_CERT): cv.string,
    vol.Optional(CONF_CONTINUOUS, default=DEFAULT_CONTINUOUS): cv.boolean,
}, extra=vol.ALLOW_EXTRA)

SUPPORT_ROOMBA = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PAUSE | \
                 SUPPORT_STOP | SUPPORT_RETURN_HOME | SUPPORT_BATTERY | \
                 SUPPORT_STATUS | SUPPORT_SEND_COMMAND


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the iRobot Roomba vacuum cleaner platform."""
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    certificate = config.get(CONF_CERT)
    continuous = config.get(CONF_CONTINUOUS)

    # Create handler
    roomba = RoombaVacuum(
        hass, name, host, username, password, certificate, continuous)
    hass.data[PLATFORM][host] = roomba

    async_add_devices([roomba], update_before_add=True)


class RoombaVacuum(VacuumDevice):
    """Representation of a Xiaomi Vacuum cleaner robot."""

    def __init__(self, hass, name, host, username, password, certificate,
                 continuous):
        """Initialize the Roomba handler."""
        self.hass = hass
        self._name = name
        self._icon = ICON
        self._host = host
        self._username = username
        self._password = password
        self._certificate = certificate
        self._continuous = continuous
        self._vacuum = None
        self._battery_level = None
        self._status = None
        self._state_attrs = {}
        self.vacuum_state = None
        self._is_on = False
        self._available = False
        self._metric = hass.config.units.is_metric

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_ROOMBA

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return self._status

    @property
    def state(self) -> str:
        """Return the state."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def vacuum(self):
        """Property accessor for vacuum object."""
        if not self._vacuum:
            from roomba import Roomba
            _LOGGER.info("Initializing with host %s (username: %s...)",
                         self._host, self._username)
            # FIXME Error handling is not currently possible since Roomba()
            # does not raise any exception on failure
            # https://github.com/NickWaterton/Roomba980-Python/issues/8
            self._vacuum = Roomba(
                address=self._host,
                blid=self._username,
                password=self._password,
                cert_name=self._certificate,
                continuous=self._continuous
            )
            self._vacuum.connect()

        return self._vacuum

    @asyncio.coroutine
    def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a vacuum command handling error messages."""
        # FIXME Error handling is not currently possible since Roomba()
        # does not raise any exception on failure
        # https://github.com/NickWaterton/Roomba980-Python/issues/8
        yield from self.hass.async_add_job(partial(func, *args, **kwargs))
        return True

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        is_on = yield from self._try_command(
            'Unable to start the vacuum: %s',
            self.vacuum.send_command, 'start')
        self._is_on = is_on

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        yield from self.async_stop()
        return_home = yield from self.async_return_to_base()
        if return_home:
            self._is_on = False

    @asyncio.coroutine
    def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        yield from self._try_command(
            "Unable to stop: %s", self.vacuum.send_command, 'stop')

    @asyncio.coroutine
    def async_start_pause(self, **kwargs):
        """Pause the cleaning task or replay it."""
        if self.vacuum_state and self.is_on:
            yield from self._try_command(
                'Unable to start/pause (pause): %s',
                self.vacuum.send_command, 'pause')
        elif self._status == 'Stopped':
            yield from self._try_command(
                'Unable to start/pause (resume): %s',
                self.vacuum.send_command, 'resume')
        else:  # vacuum is off
            yield from self._try_command(
                'Unable to start/pause (start): %s',
                self.vacuum.send_command, 'start')

    @asyncio.coroutine
    def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        return_home = yield from self._try_command(
            'Unable to return home: %s', self.vacuum.send_command, 'dock')
        if return_home:
            self._is_on = False

    @asyncio.coroutine
    def async_send_command(self, command, params, **kwargs):
        """Send raw command."""
        _LOGGER.debug('async_send_command %s (%s), %s',
                      command, params, kwargs)
        yield from self._try_command(
            "Unable to send command to the vacuum: %s",
            self.vacuum.send_command, command, params)

    @asyncio.coroutine
    def async_update(self):
        """Fetch state from the device."""
        # No data, no update
        if not self.vacuum.master_state:
            return
        state = self.vacuum.master_state.get('state', {}).get('reported', {})
        _LOGGER.debug("Got new state from the vacuum: %s", state)
        self.vacuum_state = state
        self._available = state is not None

        # Get the capabilities of our unit
        capabilities = state.get('cap', {})
        cap_pos = capabilities.get('pose', None)
        cap_bin_full = capabilities.get('binFullDetect', None)

        bin_state = state.get('bin', {})

        # Roomba software version
        software_version = state.get('softwareVer', None)

        # Error message in plain english
        error_msg = self.vacuum.error_message

        self._battery_level = state.get('batPct', None)
        self._status = self.vacuum.current_state
        self._is_on = self._status in ['Running']

        # Set properties that are to appear in the GUI
        self._state_attrs = {
            ATTR_BIN_PRESENT: bin_state.get('present', None),
            ATTR_SOFTWARE_VERSION: software_version
        }

        # Only add cleaning time and cleaned area attrs when the vacuum is
        # currently on
        if self._is_on:
            # Get clean mission status
            mission_state = state.get('cleanMissionStatus', {})
            cleaning_time = mission_state.get('mssnM', None)
            cleaned_area = mission_state.get('sqft', None)  # Imperial
            # Convert to m2 if the unit_system is set to metric
            if cleaned_area and self._metric:
                cleaned_area = round(cleaned_area * 0.0929)
            self._state_attrs[ATTR_CLEANING_TIME] = cleaning_time
            self._state_attrs[ATTR_CLEANED_AREA] = cleaned_area

        # Skip error attr if there is none
        if error_msg and error_msg != 'None':
            self._state_attrs[ATTR_ERROR] = error_msg

        # Not all Roombas expose positon data
        # https://github.com/koalazak/dorita980/issues/48
        if cap_pos == 1:
            pos_state = state.get('pose', {})
            position = None
            pos_x = pos_state.get('point', {}).get('x', None)
            pos_y = pos_state.get('point', {}).get('y', None)
            theta = pos_state.get('theta', None)
            if all(item is not None for item in [pos_x, pos_y, theta]):
                position = '({}, {}, {})'.format(pos_x, pos_y, theta)
            self._state_attrs[ATTR_POSITION] = position

        # Not all Roombas have a bin full sensor
        if cap_bin_full == 1:
            self._state_attrs[ATTR_BIN_FULL] = bin_state.get('full', None)
