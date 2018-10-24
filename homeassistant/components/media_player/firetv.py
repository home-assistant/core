"""
Support for functionality to interact with FireTV devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.firetv/
"""
import functools
import logging
import os
import time
import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, PLATFORM_SCHEMA,
    SUPPORT_SELECT_SOURCE, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET, SUPPORT_PLAY, MediaPlayerDevice)
from homeassistant.const import (
    STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING, STATE_STANDBY,
    STATE_UNKNOWN, CONF_HOST, CONF_NAME, CONF_PORT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['libusb1>=1.6.6', 'rsa>=3.4.2', 'pycryptodome>=3.6.6',
                'https://github.com/JeffLIrion/python-adb/zipball/version_bump#adb==1.3.0.1',
                'https://github.com/JeffLIrion/python-firetv/zipball/master#firetv==1.0.5.2']

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
    host = '{0}:{1}'.format(config.get(CONF_HOST), config.get(CONF_PORT))
    name = config.get(CONF_NAME)
    adbkey = config.get(CONF_ADBKEY)
    get_source = config.get(CONF_GET_SOURCE)
    get_sources = config.get(CONF_GET_SOURCES)

    device = FireTVDevice(host, name, adbkey, get_source, get_sources)
    adb_log = " using adbkey='{0}'".format(adbkey) if adbkey else ""
    if not device._firetv._adb:
        _LOGGER.warning("Could not connect to Fire TV at %s%s", host, adb_log)

        # Debugging
        if adbkey != "":
            # Check whether the key files exist
            if not os.path.exists(adbkey):
                raise FileNotFoundError(
                    "ADB private key {} does not exist".format(adbkey))
            if not os.path.exists(adbkey + ".pub"):
                raise FileNotFoundError(
                    "ADB public key {} does not exist".format(adbkey + '.pub'))

            # Check whether the key files can be read
            with open(adbkey) as _:
                pass
            with open(adbkey + '.pub') as _:
                pass

    else:
        _LOGGER.info("Setup Fire TV at %s%s", host, adb_log)
        add_devices([device])


def adb_wrapper(func):
    """A wrapper that will wait if previous ADB commands haven't finished."""
    @functools.wraps(func)
    def _adb_wrapper(self, *args, **kwargs):
        attempts = 0
        while self._adb_lock and attempts < 5:
            attempts += 1
            time.sleep(1)

        if attempts == 5 and self._adb_lock:
            self._firetv.connect()

        self._adb_lock = True
        returns = func(self, *args, **kwargs)
        self._adb_lock = False

        if returns:
            return returns

    return _adb_wrapper


class FireTVDevice(MediaPlayerDevice):
    """Representation of an Amazon Fire TV device on the network."""

    def __init__(self, host, name, adbkey, get_source, get_sources):
        """Initialize the FireTV device."""
        from firetv import FireTV
        self._host = host
        self._adbkey = adbkey
        self._firetv = FireTV(host, adbkey)
        self._adb_lock = False
        self._name = name
        self._state = STATE_UNKNOWN
        self._running_apps = None
        self._current_app = None
        self._get_source = get_source
        self._get_sources = get_sources

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
        try:
            # Check if device is disconnected.
            if not self._firetv._adb:
                self._state = STATE_UNKNOWN
                self._running_apps = None
                self._current_app = None

                # Try to connect
                self._firetv.connect()

            # Check if device is off.
            elif not self._firetv._screen_on:
                self._state = STATE_OFF
                self._running_apps = None
                self._current_app = None

            # Check if screen saver is on.
            elif not self._firetv._awake:
                self._state = STATE_IDLE
                self._running_apps = None
                self._current_app = None

            else:
                # Get the running apps.
                if self._get_sources:
                    self._running_apps = self._firetv.running_apps()

                # Get the current app.
                if self._get_source:
                    current_app = self._firetv.current_app
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
                    elif self._firetv._wake_lock:
                        self._state = STATE_PLAYING

                    # Otherwise, device is paused.
                    else:
                        self._state = STATE_PAUSED

                # Don't get the current app.
                elif self._firetv._wake_lock:
                    # Check for a wake lock (device is playing).
                    self._state = STATE_PLAYING
                else:
                    # Assume the devices is on standby.
                    self._state = STATE_STANDBY

        except:
            _LOGGER.error('Update encountered an exception; will attempt to ' +
                          're-establish the ADB connection in the next update')
            self._firetv._adb = None

    @adb_wrapper
    def turn_on(self):
        """Turn on the device."""
        self._firetv.turn_on()

    @adb_wrapper
    def turn_off(self):
        """Turn off the device."""
        self._firetv.turn_off()

    @adb_wrapper
    def media_play(self):
        """Send play command."""
        self._firetv.media_play()

    @adb_wrapper
    def media_pause(self):
        """Send pause command."""
        self._firetv.media_pause()

    @adb_wrapper
    def media_play_pause(self):
        """Send play/pause command."""
        self._firetv.media_play_pause()

    @adb_wrapper
    def media_stop(self):
        """Send stop (back) command."""
        self._firetv.back()

    @adb_wrapper
    def volume_up(self):
        """Send volume up command."""
        self._firetv.volume_up()

    @adb_wrapper
    def volume_down(self):
        """Send volume down command."""
        self._firetv.volume_down()

    @adb_wrapper
    def media_previous_track(self):
        """Send previous track command (results in rewind)."""
        self._firetv.media_previous()

    @adb_wrapper
    def media_next_track(self):
        """Send next track command (results in fast-forward)."""
        self._firetv.media_next()

    @adb_wrapper
    def select_source(self, source):
        """Select input source."""
        if isinstance(source, str):
            if not source.startswith('!'):
                self._firetv.launch_app(source)
            else:
                self._firetv.stop_app(source[1:].lstrip())
