"""
Provide functionality to interact with AndroidTv devices on the network.

Example config using an external ADB server:
media_player:
  - platform: androidtv
    host: 192.168.1.37
    name: MIBOX3
    adb_server_ip: 127.0.0.1
    adb_server_port: 5037
    apps:
      "amazon": "Amazon Premium Video"

Example config using purely Python:
media_player:
  - platform: androidtv
    host: 192.168.1.37
    name: MIBOX3
    adbkey: /config/adbkey
    apps:
      "amazon": "Amazon Premium Video"

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.androidtv/
"""

import logging
import functools
import os
import threading
import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN, MediaPlayerDevice, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE, SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP)

from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT,
    STATE_IDLE, STATE_PAUSED, STATE_PLAYING, STATE_OFF)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['androidtv==0.0.4']

_LOGGER = logging.getLogger(__name__)

CONF_APPS = 'apps'
CONF_ADBKEY = 'adbkey'
CONF_ADB_SERVER_IP = 'adb_server_ip'
CONF_ADB_SERVER_PORT = 'adb_server_port'

DEFAULT_APPS = {}
DEFAULT_ADBKEY = os.path.join(os.path.expanduser('~'), '.android', 'adbkey')
DEFAULT_NAME = 'Android'
DEFAULT_PORT = '5555'
DEFAULT_ADB_SERVER_PORT = 5037


def has_adb_files(value):
    """Check that ADB key files exist."""
    priv_key = value
    pub_key = '{}.pub'.format(value)
    cv.isfile(pub_key)
    return cv.isfile(priv_key)


ACTIONS = {
    "back": "4",
    "blue": "186",
    "component1": "249",
    "component2": "250",
    "composite1": "247",
    "composite2": "248",
    "down": "20",
    "end": "123",
    "enter": "66",
    "green": "184",
    "hdmi1": "243",
    "hdmi2": "244",
    "hdmi3": "245",
    "hdmi4": "246",
    "home": "3",
    "input": "178",
    "left": "21",
    "menu": "82",
    "move_home": "122",
    "mute": "164",
    "pairing": "225",
    "power": "26",
    "resume": "224",
    "right": "22",
    "sat": "237",
    "search": "84",
    "settings": "176",
    "sleep": "223",
    "suspend": "276",
    "sysdown": "281",
    "sysleft": "282",
    "sysright": "283",
    "sysup": "280",
    "text": "233",
    "top": "122",
    "up": "19",
    "vga": "251",
    "voldown": "25",
    "volup": "24",
    "yellow": "185"
}

KNOWN_APPS = {
    "amazon": "Amazon Prime Video",
    "dream": "Screensaver",
    "kodi": "Kodi",
    "netflix": "Netflix",
    "plex": "Plex",
    "spotify": "Spotify",
    "tvlauncher": "Homescreen",
    "youtube": "Youtube",
    "zatto": "Zattoo"
}

SUPPORT_ANDROIDTV = (SUPPORT_NEXT_TRACK | SUPPORT_PAUSE |
                     SUPPORT_PLAY | SUPPORT_PREVIOUS_TRACK |
                     SUPPORT_TURN_OFF | SUPPORT_TURN_ON |
                     SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP |
                     SUPPORT_STOP)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(cv.port, cv.string),
    vol.Optional(CONF_ADBKEY): has_adb_files,
    vol.Optional(CONF_APPS, default=DEFAULT_APPS): dict,
    vol.Optional(CONF_ADB_SERVER_IP): cv.string,
    vol.Optional(
        CONF_ADB_SERVER_PORT, default=DEFAULT_ADB_SERVER_PORT): cv.port
})

ACTION_SERVICE = 'androidtv_action'
INTENT_SERVICE = 'androidtv_intent'
KEY_SERVICE = 'androidtv_key'

SERVICE_ACTION_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required('action'): vol.In(ACTIONS),
})

SERVICE_INTENT_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required('intent'): cv.string,
})

SERVICE_KEY_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required('key'): cv.string,
})

DATA_KEY = '{}.androidtv'.format(DOMAIN)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the androidtv platform."""
    from androidtv import AndroidTV
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = '{0}:{1}'.format(config[CONF_HOST], config[CONF_PORT])
    name = config.get(CONF_NAME)

    if CONF_ADB_SERVER_IP not in config:
        atv = AndroidTV(host)
        if not atv.available:
            # "python-adb" with adbkey
            if CONF_ADBKEY in config:
                adbkey = config[CONF_ADBKEY]
            else:
                adbkey = DEFAULT_ADBKEY
            atv = AndroidTV(host, adbkey)
            adb_log = " using adbkey='{0}'".format(adbkey)
        else:
            adb_log = ""

    else:
        # "pure-python-adb"
        atv = AndroidTV(
            host,
            adb_server_ip=config[CONF_ADB_SERVER_IP],
            adb_server_port=config[CONF_ADB_SERVER_PORT])
        adb_log = " using ADB server at {0}:{1}".format(
            config[CONF_ADB_SERVER_IP], config[CONF_ADB_SERVER_PORT])

    if not atv.available:
        _LOGGER.warning(
            "Could not connect to Android TV at %s%s", host, adb_log)
        raise PlatformNotReady

    if host in hass.data[DATA_KEY]:
        _LOGGER.warning("Platform already setup on %s, skipping.", host)
    else:
        device = AndroidTVDevice(atv, name, config[CONF_APPS])
        add_entities([device])
        _LOGGER.info("Setup Android TV at %s%s", host, adb_log)
        hass.data[DATA_KEY][host] = device

    def service_action(service):
        """Dispatch service calls to target entities."""
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}

        entity_id = service.data.get(ATTR_ENTITY_ID)
        target_devices = [dev for dev in hass.data[DATA_KEY].values()
                          if dev.entity_id in entity_id]

        for target_device in target_devices:
            target_device.do_action(params['action'])

    def service_intent(service):
        """Dispatch service calls to target entities."""
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}

        entity_id = service.data.get(ATTR_ENTITY_ID)
        target_devices = [dev for dev in hass.data[DATA_KEY].values()
                          if dev.entity_id in entity_id]

        for target_device in target_devices:
            target_device.start_intent(params['intent'])

    def service_key(service):
        """Dispatch service calls to target entities."""
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}

        entity_id = service.data.get(ATTR_ENTITY_ID)
        target_devices = [dev for dev in hass.data[DATA_KEY].values()
                          if dev.entity_id in entity_id]

        for target_device in target_devices:
            target_device.input_key(params['key'])

    hass.services.register(
        DOMAIN, ACTION_SERVICE, service_action, schema=SERVICE_ACTION_SCHEMA)
    hass.services.register(
        DOMAIN, INTENT_SERVICE, service_intent, schema=SERVICE_INTENT_SCHEMA)
    hass.services.register(
        DOMAIN, KEY_SERVICE, service_key, schema=SERVICE_KEY_SCHEMA)


def adb_decorator(override_available=False):
    """Send an ADB command if the device is available and not locked."""
    def adb_wrapper(func):
        """Wait if previous ADB commands haven't finished."""
        @functools.wraps(func)
        def _adb_wrapper(self, *args, **kwargs):
            # If the device is unavailable, don't do anything
            if not self.available and not override_available:
                return None

            # "python-adb"
            if not self.androidtv.adb_server_ip:
                # If an ADB command is already running, skip this command
                if not self.adb_lock.acquire(blocking=False):
                    _LOGGER.info('Skipping an ADB command because a previous '
                                 'command is still running')
                    return None

                # More ADB commands will be prevented while trying this one
                try:
                    returns = func(self, *args, **kwargs)
                except self.exceptions:
                    _LOGGER.error('Failed to execute an ADB command;'
                                  ' will attempt to re-establish the ADB'
                                  ' connection in the next update')
                    returns = None
                    _LOGGER.warning(
                        "Device %s became unavailable.", self._name)
                    self._available = False  # pylint: disable=protected-access
                finally:
                    self.adb_lock.release()

            # "pure-python-adb"
            else:
                try:
                    returns = func(self, *args, **kwargs)
                except self.exceptions:
                    _LOGGER.error('Failed to execute an ADB command;'
                                  ' will attempt to re-establish the ADB'
                                  ' connection in the next update')
                    returns = None
                    _LOGGER.warning(
                        "Device %s became unavailable.", self._name)
                    self._available = False  # pylint: disable=protected-access

            return returns

        return _adb_wrapper

    return adb_wrapper


class AndroidTVDevice(MediaPlayerDevice):
    """Representation of an Android TV device."""

    def __init__(self, atv, name, apps):
        """Initialize the Android TV device."""
        self.androidtv = atv

        self._name = name
        self._apps = KNOWN_APPS
        self._apps.update(dict(apps))
        self._app_name = None
        self._state = None
        self._muted = None
        self._available = self.androidtv.available
        self._properties = self.androidtv.properties
        self._unique_id = 'androitv-{}-{}'.format(
            name, self._properties['serialno'])

        # whether or not the ADB connection is currently in use
        self.adb_lock = threading.Lock()

        # ADB exceptions to catch
        if not self.androidtv.adb_server_ip:
            # "python-adb"
            from adb.adb_protocol import (
                InvalidChecksumError, InvalidCommandError,
                InvalidResponseError)
            from adb.usb_exceptions import TcpTimeoutException
            self.exceptions = (AttributeError, BrokenPipeError, TypeError,
                               ValueError, InvalidChecksumError,
                               InvalidCommandError, InvalidResponseError,
                               TcpTimeoutException)
        else:
            # "pure-python-adb"
            self.exceptions = (ConnectionResetError,)

    @adb_decorator(override_available=True)
    def update(self):
        """Update the states of the device."""
        # Check if device is disconnected.
        if not self._available:
            # Try to connect
            self._available = self.androidtv.connect()

            if self._available:
                _LOGGER.info("Device %s reconnected.", self._name)

        # If the ADB connection is not intact, don't update.
        if not self._available:
            return

        success = self.androidtv.update()
        if not success:
            _LOGGER.warning(
                "Device %s became unavailable.", self._name)
            self._available = False
            return

        self._app_name = self.get_app_name(self.androidtv.app_id)

        if self.androidtv.state == 'off':
            self._state = STATE_OFF
        elif self.androidtv.state == 'idle':
            self._state = STATE_IDLE
        elif self.androidtv.state == 'playing':
            self._state = STATE_PLAYING
        elif self.androidtv.state == 'paused':
            self._state = STATE_PAUSED

    def get_app_name(self, app_id):
        """Return the app name from its id and known apps."""
        if app_id is None:
            return None
        for app in self._apps:
            if app in app_id['package']:
                app_name = self._apps[app]
                break
        else:
            app_name = None

        return app_name

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.androidtv.muted

    @property
    def volume_level(self):
        """Return the volume level."""
        return self.androidtv.volume

    @property
    def source(self):
        """Return the current playback device."""
        return self.androidtv.device

    @property
    def app_id(self):
        """ID of the current running app."""
        return self.androidtv.app_id

    @property
    def app_name(self):
        """Name of the current running app."""
        return self._app_name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ANDROIDTV

    @property
    def unique_id(self):
        """Return the device unique id."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            'connections': {
                (dr.CONNECTION_NETWORK_MAC, self._properties['wifimac'])
            },
            'identifiers': {
                (DOMAIN, self._unique_id)
            },
            'name': self._name,
            'manufacturer': self._properties['manufacturer'],
            'model': self._properties['model'],
            'sw_version': self._properties['sw_version'],
        }

    @adb_decorator()
    def turn_on(self):
        """Instruct the tv to turn on."""
        self.androidtv.turn_on()

    @adb_decorator()
    def turn_off(self):
        """Instruct the tv to turn off."""
        self.androidtv.turn_off()

    @adb_decorator()
    def media_play(self):
        """Send play command."""
        self.androidtv.media_play()
        self._state = STATE_PLAYING

    @adb_decorator()
    def media_pause(self):
        """Send pause command."""
        self.androidtv.media_pause()
        self._state = STATE_PAUSED

    @adb_decorator()
    def media_play_pause(self):
        """Send play/pause command."""
        self.androidtv.media_play_pause()

    @adb_decorator()
    def media_stop(self):
        """Send stop command."""
        self.androidtv.media_stop()
        self._state = STATE_IDLE

    @adb_decorator()
    def mute_volume(self, mute):
        """Mute the volume."""
        self.androidtv.mute_volume()
        self._muted = mute

    @adb_decorator()
    def volume_up(self):
        """Increment the volume level."""
        self.androidtv.volume_up()

    @adb_decorator()
    def volume_down(self):
        """Decrement the volume level."""
        self.androidtv.volume_down()

    @adb_decorator()
    def media_previous_track(self):
        """Send previous track command."""
        self.androidtv.media_previous()

    @adb_decorator()
    def media_next_track(self):
        """Send next track command."""
        self.androidtv.media_next()

    @adb_decorator()
    def input_key(self, key):
        """Input the key to the device."""
        self.androidtv.input_key(key)

    @adb_decorator()
    def start_intent(self, uri):
        """Start an intent on the device."""
        self.androidtv.start_intent(uri)

    @adb_decorator()
    def do_action(self, action):
        """Input the key corresponding to the action."""
        self.androidtv.do_action(action)
