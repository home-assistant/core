"""
Support for functionality to interact with FireTV devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.firetv/
"""
import functools
import logging
import os
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_SET, )
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_IDLE, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING, STATE_STANDBY)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['firetv==1.0.7']

_LOGGER = logging.getLogger(__name__)

SUPPORT_FIRETV = SUPPORT_PAUSE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_NEXT_TRACK | SUPPORT_SELECT_SOURCE | SUPPORT_STOP | \
    SUPPORT_VOLUME_SET | SUPPORT_PLAY

CONF_ADBKEY = 'adbkey'
CONF_GET_SOURCE = 'get_source'
CONF_GET_SOURCES = 'get_sources'

DEFAULT_NAME = 'Amazon Fire TV'
DEFAULT_PORT = 5555
DEFAULT_ADBKEY = ''
DEFAULT_GET_SOURCE = True
DEFAULT_GET_SOURCES = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_ADBKEY, default=DEFAULT_ADBKEY): cv.string,
    vol.Optional(CONF_GET_SOURCE, default=DEFAULT_GET_SOURCE): cv.boolean,
    vol.Optional(CONF_GET_SOURCES, default=DEFAULT_GET_SOURCES): cv.boolean
})

PACKAGE_LAUNCHER = "com.amazon.tv.launcher"
PACKAGE_SETTINGS = "com.amazon.tv.settings"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the FireTV platform."""
    host = '{0}:{1}'.format(config[CONF_HOST], config[CONF_PORT])
    name = config[CONF_NAME]
    adbkey = config[CONF_ADBKEY]
    get_source = config[CONF_GET_SOURCE]
    get_sources = config[CONF_GET_SOURCES]

    device = FireTVDevice(host, name, adbkey, get_source, get_sources)
    adb_log = " using adbkey='{0}'".format(adbkey) if adbkey else ""
    if not device.firetv.adb:
        _LOGGER.warning("Could not connect to Fire TV at %s%s", host, adb_log)

        # Configuration troubleshooting for `adbkey`
        if adbkey:
            # Check whether the key files exist
            if not os.path.exists(adbkey):
                raise FileNotFoundError(
                    "ADB private key {} does not exist".format(adbkey))
            if not os.path.exists(adbkey + ".pub"):
                raise FileNotFoundError(
                    "ADB public key {} does not exist".format(adbkey + '.pub'))

            # Check whether the key files can be read
            with open(adbkey):
                pass
            with open(adbkey + '.pub'):
                pass

    else:
        _LOGGER.info("Setup Fire TV at %s%s", host, adb_log)
        add_devices([device])


def adb_wrapper(func):
    """Wait if previous ADB commands haven't finished."""
    @functools.wraps(func)
    def _adb_wrapper(self, *args, **kwargs):
        # If an ADB command is already running, don't execute this command
        if self.firetv.adb and self.adb_lock:
            _LOGGER.info('Skipping an ADB command because a previous command '
                         'is still running')
            return

        # Prevent additional ADB commands while trying to run this command
        self.adb_lock = True
        try:
            returns = func(self, *args, **kwargs)
        except self.exceptions:
            _LOGGER.error('Failed to execute an ADB command; will attempt to '
                          're-establish the ADB connection in the next update')
            returns = None
            self.firetv.adb = None
        finally:
            self.adb_lock = False

        return returns

    return _adb_wrapper


class FireTVDevice(MediaPlayerDevice):
    """Representation of an Amazon Fire TV device on the network."""

    def __init__(self, host, name, adbkey, get_source, get_sources):
        """Initialize the FireTV device."""
        from firetv import FireTV  # pylint: disable=no-name-in-module
        from adb.adb_protocol import (
            InvalidCommandError, InvalidResponseError, InvalidChecksumError)

        self._host = host
        self._name = name
        self._adbkey = adbkey
        self._get_source = get_source
        self._get_sources = get_sources

        self.firetv = FireTV(host, adbkey)

        # whether or not the ADB connection is currently in use
        self.adb_lock = False

        # ADB exceptions to catch
        self.exceptions = (TypeError, ValueError, AttributeError,
                           InvalidCommandError, InvalidResponseError,
                           InvalidChecksumError)

        self._state = None
        self._available = bool(self.firetv.adb)
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
    def source(self):
        """Return the current app."""
        return self._current_app

    @property
    def source_list(self):
        """Return a list of running apps."""
        return self._running_apps

    @adb_wrapper
    def update(self):
        """Get the latest date and update device state."""
        # Check if device is disconnected.
        if not self.firetv.adb:
            self._available = False
            self._running_apps = None
            self._current_app = None

            # Try to connect
            self.firetv.connect()

        else:
            self._available = True

            # Check if device is off.
            if not self.firetv.screen_on:
                self._state = STATE_OFF
                self._running_apps = None
                self._current_app = None

            # Check if screen saver is on.
            elif not self.firetv.awake:
                self._state = STATE_IDLE
                self._running_apps = None
                self._current_app = None

            else:
                # Get the running apps.
                if self._get_sources:
                    self._running_apps = self.firetv.running_apps

                # Get the current app.
                if self._get_source:
                    current_app = self.firetv.current_app
                    if isinstance(current_app, dict)\
                            and 'package' in current_app:
                        self._current_app = current_app['package']
                    else:
                        self._current_app = current_app

                    # Show the current app as the only running app.
                    if not self._get_sources:
                        if self._current_app:
                            self._running_apps = [self._current_app]
                        else:
                            self._running_apps = None

                    # Check if the launcher is active.
                    if self._current_app in [PACKAGE_LAUNCHER,
                                             PACKAGE_SETTINGS]:
                        self._state = STATE_STANDBY

                    # Check for a wake lock (device is playing).
                    elif self.firetv.wake_lock:
                        self._state = STATE_PLAYING

                    # Otherwise, device is paused.
                    else:
                        self._state = STATE_PAUSED

                # Don't get the current app.
                elif self.firetv.wake_lock:
                    # Check for a wake lock (device is playing).
                    self._state = STATE_PLAYING
                else:
                    # Assume the devices is on standby.
                    self._state = STATE_STANDBY

    @adb_wrapper
    def turn_on(self):
        """Turn on the device."""
        self.firetv.turn_on()

    @adb_wrapper
    def turn_off(self):
        """Turn off the device."""
        self.firetv.turn_off()

    @adb_wrapper
    def media_play(self):
        """Send play command."""
        self.firetv.media_play()

    @adb_wrapper
    def media_pause(self):
        """Send pause command."""
        self.firetv.media_pause()

    @adb_wrapper
    def media_play_pause(self):
        """Send play/pause command."""
        self.firetv.media_play_pause()

    @adb_wrapper
    def media_stop(self):
        """Send stop (back) command."""
        self.firetv.back()

    @adb_wrapper
    def volume_up(self):
        """Send volume up command."""
        self.firetv.volume_up()

    @adb_wrapper
    def volume_down(self):
        """Send volume down command."""
        self.firetv.volume_down()

    @adb_wrapper
    def media_previous_track(self):
        """Send previous track command (results in rewind)."""
        self.firetv.media_previous()

    @adb_wrapper
    def media_next_track(self):
        """Send next track command (results in fast-forward)."""
        self.firetv.media_next()

    @adb_wrapper
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
