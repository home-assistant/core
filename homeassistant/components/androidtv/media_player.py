"""
Support for functionality to interact with FireTV devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.firetv/
"""
import functools
import logging
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON)
from homeassistant.const import (
    ATTR_COMMAND, ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT, STATE_IDLE,
    STATE_OFF, STATE_PAUSED, STATE_PLAYING, STATE_STANDBY)
import homeassistant.helpers.config_validation as cv

FIRETV_DOMAIN = 'firetv'

REQUIREMENTS = ['firetv==1.0.9']

_LOGGER = logging.getLogger(__name__)

SUPPORT_FIRETV = SUPPORT_PAUSE | SUPPORT_PLAY | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_NEXT_TRACK | SUPPORT_SELECT_SOURCE | SUPPORT_STOP

CONF_ADBKEY = 'adbkey'
CONF_ADB_SERVER_IP = 'adb_server_ip'
CONF_ADB_SERVER_PORT = 'adb_server_port'
CONF_APPS = 'apps'
CONF_GET_SOURCES = 'get_sources'

DEFAULT_NAME = 'Amazon Fire TV'
DEFAULT_PORT = 5555
DEFAULT_ADB_SERVER_PORT = 5037
DEFAULT_GET_SOURCES = True
DEFAULT_APPS = {}

SERVICE_ADB_COMMAND = 'adb_command'

SERVICE_ADB_COMMAND_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_COMMAND): cv.string,
})


def has_adb_files(value):
    """Check that ADB key files exist."""
    priv_key = value
    pub_key = '{}.pub'.format(value)
    cv.isfile(pub_key)
    return cv.isfile(priv_key)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_ADBKEY): has_adb_files,
    vol.Optional(CONF_ADB_SERVER_IP): cv.string,
    vol.Optional(
        CONF_ADB_SERVER_PORT, default=DEFAULT_ADB_SERVER_PORT): cv.port,
    vol.Optional(CONF_GET_SOURCES, default=DEFAULT_GET_SOURCES): cv.boolean,
    vol.Optional(
        CONF_APPS, default=DEFAULT_APPS): vol.Schema({cv.string: cv.string})
})

# Translate from `FireTV` reported state to HA state.
FIRETV_STATES = {'off': STATE_OFF,
                 'idle': STATE_IDLE,
                 'standby': STATE_STANDBY,
                 'playing': STATE_PLAYING,
                 'paused': STATE_PAUSED}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the FireTV platform."""
    from firetv import FireTV

    hass.data.setdefault(FIRETV_DOMAIN, {})

    host = '{0}:{1}'.format(config[CONF_HOST], config[CONF_PORT])

    if CONF_ADB_SERVER_IP not in config:
        # Use "python-adb" (Python ADB implementation)
        if CONF_ADBKEY in config:
            ftv = FireTV(host, config[CONF_ADBKEY])
            adb_log = " using adbkey='{0}'".format(config[CONF_ADBKEY])
        else:
            ftv = FireTV(host)
            adb_log = ""
    else:
        # Use "pure-python-adb" (communicate with ADB server)
        ftv = FireTV(host, adb_server_ip=config[CONF_ADB_SERVER_IP],
                     adb_server_port=config[CONF_ADB_SERVER_PORT])
        adb_log = " using ADB server at {0}:{1}".format(
            config[CONF_ADB_SERVER_IP], config[CONF_ADB_SERVER_PORT])

    if not ftv.available:
        _LOGGER.warning("Could not connect to Fire TV at %s%s", host, adb_log)
        return

    name = config[CONF_NAME]
    get_sources = config[CONF_GET_SOURCES]
    apps = config[CONF_APPS]

    if host in hass.data[FIRETV_DOMAIN]:
        _LOGGER.warning("Platform already setup on %s, skipping", host)
    else:
        device = FireTVDevice(ftv, name, get_sources, apps)
        add_entities([device])
        _LOGGER.debug("Setup Fire TV at %s%s", host, adb_log)
        hass.data[FIRETV_DOMAIN][host] = device

    if hass.services.has_service(FIRETV_DOMAIN, SERVICE_ADB_COMMAND):
        return

    def service_adb_command(service):
        """Dispatch service calls to target entities."""
        cmd = service.data.get(ATTR_COMMAND)
        entity_id = service.data.get(ATTR_ENTITY_ID)
        target_devices = [dev for dev in hass.data[FIRETV_DOMAIN].values()
                          if dev.entity_id in entity_id]

        for target_device in target_devices:
            output = target_device.adb_command(cmd)

            # log the output if there is any
            if output:
                _LOGGER.info("Output of command '%s' from '%s': %s",
                             cmd, target_device.entity_id, repr(output))

    hass.services.register(FIRETV_DOMAIN, SERVICE_ADB_COMMAND,
                           service_adb_command,
                           schema=SERVICE_ADB_COMMAND_SCHEMA)


def adb_decorator(override_available=False):
    """Send an ADB command if the device is available and catch exceptions."""
    def _adb_decorator(func):
        """Wait if previous ADB commands haven't finished."""
        @functools.wraps(func)
        def _adb_exception_catcher(self, *args, **kwargs):
            # If the device is unavailable, don't do anything
            if not self.available and not override_available:
                return None

            try:
                return func(self, *args, **kwargs)
            except self.exceptions as err:
                _LOGGER.error(
                    "Failed to execute an ADB command. ADB connection re-"
                    "establishing attempt in the next update. Error: %s", err)
                self._available = False  # pylint: disable=protected-access
                return None

        return _adb_exception_catcher

    return _adb_decorator


class FireTVDevice(MediaPlayerDevice):
    """Representation of an Amazon Fire TV device on the network."""

    def __init__(self, ftv, name, get_sources, apps):
        """Initialize the FireTV device."""
        from firetv import APPS, KEYS
        self.apps = APPS
        self.keys = KEYS

        self.apps.update(apps)

        self.firetv = ftv

        self._name = name
        self._get_sources = get_sources

        # ADB exceptions to catch
        if not self.firetv.adb_server_ip:
            # Using "python-adb" (Python ADB implementation)
            from adb.adb_protocol import (InvalidChecksumError,
                                          InvalidCommandError,
                                          InvalidResponseError)
            from adb.usb_exceptions import TcpTimeoutException

            self.exceptions = (AttributeError, BrokenPipeError, TypeError,
                               ValueError, InvalidChecksumError,
                               InvalidCommandError, InvalidResponseError,
                               TcpTimeoutException)
        else:
            # Using "pure-python-adb" (communicate with ADB server)
            self.exceptions = (ConnectionResetError,)

        self._state = None
        self._available = self.firetv.available
        self._current_app = None
        self._running_apps = None

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_FIRETV

    @property
    def state(self):
        """Return the state of the player."""
        return self._state

    @property
    def available(self):
        """Return whether or not the ADB connection is valid."""
        return self._available

    @property
    def app_id(self):
        """Return the current app."""
        return self._current_app

    @property
    def app_name(self):
        """Return the friendly name of the current app."""
        return self.apps.get(self._current_app, self._current_app)

    @property
    def source(self):
        """Return the current app."""
        return self._current_app

    @property
    def source_list(self):
        """Return a list of running apps."""
        return self._running_apps

    @adb_decorator(override_available=True)
    def update(self):
        """Update the device state and, if necessary, re-connect."""
        # Check if device is disconnected.
        if not self._available:
            # Try to connect
            self._available = self.firetv.connect()

            # To be safe, wait until the next update to run ADB commands.
            return

        # If the ADB connection is not intact, don't update.
        if not self._available:
            return

        # Get the `state`, `current_app`, and `running_apps`.
        ftv_state, self._current_app, self._running_apps = \
            self.firetv.update(self._get_sources)

        self._state = FIRETV_STATES[ftv_state]

    @adb_decorator()
    def turn_on(self):
        """Turn on the device."""
        self.firetv.turn_on()

    @adb_decorator()
    def turn_off(self):
        """Turn off the device."""
        self.firetv.turn_off()

    @adb_decorator()
    def media_play(self):
        """Send play command."""
        self.firetv.media_play()

    @adb_decorator()
    def media_pause(self):
        """Send pause command."""
        self.firetv.media_pause()

    @adb_decorator()
    def media_play_pause(self):
        """Send play/pause command."""
        self.firetv.media_play_pause()

    @adb_decorator()
    def media_stop(self):
        """Send stop (back) command."""
        self.firetv.back()

    @adb_decorator()
    def volume_up(self):
        """Send volume up command."""
        self.firetv.volume_up()

    @adb_decorator()
    def volume_down(self):
        """Send volume down command."""
        self.firetv.volume_down()

    @adb_decorator()
    def media_previous_track(self):
        """Send previous track command (results in rewind)."""
        self.firetv.media_previous()

    @adb_decorator()
    def media_next_track(self):
        """Send next track command (results in fast-forward)."""
        self.firetv.media_next()

    @adb_decorator()
    def select_source(self, source):
        """Select input source.

        If the source starts with a '!', then it will close the app instead of
        opening it.
        """
        if isinstance(source, str):
            if not source.startswith('!'):
                self.firetv.launch_app(source)
            else:
                self.firetv.stop_app(source[1:].lstrip())

    @adb_decorator()
    def adb_command(self, cmd):
        """Send an ADB command to a Fire TV device."""
        key = self.keys.get(cmd)
        if key:
            return self.firetv.adb_shell('input keyevent {}'.format(key))
        return self.firetv.adb_shell(cmd)
