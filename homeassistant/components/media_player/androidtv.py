# /usr/bin/python3
"""
Provide functionality to interact with AndroidT devices on the network.
Example config:

media_player:
  - platform: androidtv
    devices:
      192.168.1.37:
        name: MIBOX3 ANDROID TV
        port: 5555
        scan_interval: 10

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.androidtv/
"""

import logging
from datetime import timedelta
import voluptuous as vol

from homeassistant.components.media_player import (
    DOMAIN, MediaPlayerDevice, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE, SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP)

from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_DEVICES, CONF_NAME, CONF_PORT,
    CONF_SCAN_INTERVAL, STATE_IDLE, STATE_PAUSED, STATE_PLAYING, STATE_OFF)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval

REQUIREMENTS = ['pure-python-adb==0.1.5.dev0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Android'
DEFAULT_PORT = 5555
SCAN_INTERVAL = timedelta(seconds=10)

SUPPORT_ANDROIDTV = (SUPPORT_NEXT_TRACK | SUPPORT_PAUSE |
                     SUPPORT_PLAY | SUPPORT_PREVIOUS_TRACK |
                     SUPPORT_TURN_OFF | SUPPORT_TURN_ON |
                     SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP |
                     SUPPORT_STOP)


DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}, })

KNOWN_APPS = {
    "dream": "Screensaver",
    "kodi": "Kodi",
    "netfilx": "Netflix",
    "plex": "Plex",
    "spotify": "Spotify",
    "tvlauncher": "Homescreen",
    "youtube": "Youtube"
}

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

DATA_KEY = '{}.androidtv'.format(DOMAIN)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the androidtv platform."""

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    from adb.client import Client as AdbClient
    client = AdbClient(host="127.0.0.1", port=5037)

    androidtvs = []
    for host, device_config in config[CONF_DEVICES].items():
        name = device_config[CONF_NAME]
        port = str(device_config[CONF_PORT])
        scan_interval = device_config[CONF_SCAN_INTERVAL]
        uri = host + ':' + port

        try:
            adb_device = client.device(uri)
            if adb_device is None:
                _LOGGER.error(
                    "Can't reach adb server, is it running ?")
                raise PlatformNotReady

            device = {'name': name,
                      'ipaddr': host,
                      'port': port,
                      'scan_interval': scan_interval}
            androidtv = AndroidTv(device)
            androidtvs.append(androidtv)
            hass.data[DATA_KEY][host] = androidtv
        except RuntimeError:
            _LOGGER.error(
                "Can't reach adb server, is it running ?")
            raise PlatformNotReady

    add_entities(androidtvs, True)

    def service(service):
        """Dispatch service calls to target entities."""
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}

        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            target_devices = [dev for dev in hass.data[DATA_KEY].values()
                              if dev.entity_id in entity_ids]
        else:
            target_devices = hass.data[DATA_KEY].values()

        for target_device in target_devices:
            if len(params.keys()) == 1:
                if 'action' in params:
                    target_device.do_action(params['action'])
                elif 'intent' in params:
                    target_device.start_intent(params['intent'])
                elif 'key' in params:
                    target_device.input_key(params['key'])

    hass.services.register(DOMAIN, 'androidtv_action', service)


class AndroidTv(MediaPlayerDevice):
    """Representation of an AndroidTv device."""

    def __init__(self, device):
        """Initialize the Android device."""
        from adb.client import Client as AdbClient
        host = device['ipaddr']
        port = device['port']
        name = device['name']
        scan_interval = device['scan_interval']
        self._scan_interval = scan_interval

        self._uri = host + ':' + port
        self._client = AdbClient(host="127.0.0.1", port=5037)
        self._device = self._client.device(self._uri)

        self._name = name
        self._available = None
        self._volume = None
        self._muted = None
        self._state = None
        self._app_id = None
        self._app_name = None
        self._device = None
        _LOGGER.info("its all good man")

    def _init_regular_updates(self):
        """Schedule regular updates at the specified interval."""
        track_time_interval(
            self._hass, lambda now: self.update(), self._scan_interval)

    def update(self):
        """Get the latest details from the device."""
        try:
            adb_devices = self._client.devices()
        except RuntimeError:
            # Can't connect to adb server
            if self._available:
                _LOGGER.error(
                    "Can't reach adb server, is it running ?")
                _LOGGER.warning(
                    "Device {} became unavailable.".format(self._name))
                self._available = False
        else:
            if any([self._uri in host.get_serial_no() for host in adb_devices]):
                # Device is connected through the ADB server
                if not self._available:
                    _LOGGER.info("Device {} reconnected.".format(self._name))
                    self._available = True

                power_output = self._device.shell('dumpsys power')
                audio_output = self._device.shell('dumpsys audio')
                win_output = self._device.shell('dumpsys window windows')

                self._state = self.get_state(power_output, audio_output)
                self._muted, self._device, self._volume = self.get_audio(
                    audio_output)
                self._app_id = self.get_app_id(win_output)
                self._app_name = self.get_app_name(self._app_id)

            elif self._available:
                _LOGGER.error(
                    "ADB server not connected to {}".format(self._name))
                _LOGGER.warning(
                    "Device {} became unavailable.".format(self._name))
                self._available = False

    def get_state(self, power_output, audio_output):
        """Process sys outputs and return the device state."""
        if 'Display Power: state=ON' not in power_output:
            return STATE_OFF
        elif 'started' in audio_output:
            state = STATE_PLAYING
        elif 'paused' in audio_output:
            state = STATE_PAUSED
        else:
            state = STATE_IDLE

        return state

    def get_audio(self, audio_output):
        """Process sys output and return the volume, muted state and device."""
        import re
        block_pattern = 'STREAM_MUSIC(.*?)- STREAM'
        stream_block = re.findall(
            block_pattern, audio_output, re.DOTALL | re.MULTILINE)[0]

        device_pattern = 'Devices: (.*?)\W'
        device = re.findall(device_pattern, stream_block,
                            re.DOTALL | re.MULTILINE)[0]

        muted_pattern = 'Muted: (.*?)\W'
        muted = re.findall(muted_pattern, stream_block,
                           re.DOTALL | re.MULTILINE)[0]

        volume_pattern = device + '\): (\d{1,})'
        volume_level = re.findall(
            volume_pattern, stream_block, re.DOTALL | re.MULTILINE)[0]

        if muted == 'true':
            muted = True
        else:
            muted = False

        volume = round(1/15 * int(volume_level), 2)

        return muted, device, volume

    def get_app_id(self, win_output):
        """Process sys output and return the current app id."""
        win_output = win_output.splitlines()
        for line in win_output:
            if 'mCurrentFocus' in line:
                current_app = line.split(' ')[4].split('/')[0]
                return current_app
        return None

    def get_app_name(self, app_id):
        """Return the app name from its id and known apps."""
        i = 0
        for app in KNOWN_APPS:
            if app in app_id:
                app_name = KNOWN_APPS[app]
                i += 1
        if i == 0:
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
        return self._muted

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._volume

    @property
    def source(self):
        """Return the current playback device."""
        return self._device

    @property
    def app_id(self):
        """ID of the current running app."""
        return self._app_id

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

    def turn_on(self):
        """Instruct the tv to turn on."""
        self._device.shell('input keyevent 26')

    def turn_off(self):
        """Instruct the tv to turn off."""
        self._device.shell('input keyevent 26')

    def media_play(self):
        """Send play command."""
        self._device.shell('input keyevent 126')
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self._device.shell('input keyevent 127')
        self._state = STATE_PAUSED

    def media_play_pause(self):
        """Send play/pause command."""
        self._device.shell('input keyevent 85')

    def media_stop(self):
        """Send stop command."""
        self._device.shell('input keyevent 86')
        self._state = STATE_IDLE

    def mute_volume(self, mute):
        """Mute the volume."""
        self._device.shell('input keyevent 164')
        self._muted = mute

    def volume_up(self):
        """"Increment the volume level."""
        self._device.shell('input keyevent 24')

    def volume_down(self):
        """"Decrement the volume level."""
        self._device.shell('input keyevent 25')

    def media_previous_track(self):
        """Send previous track command."""
        self._device.shell('input keyevent 88')

    def media_next_track(self):
        """Send next track command."""
        self._device.shell('input keyevent 87')

    def input_key(self, key):
        """Input the key to the device."""
        _LOGGER.info('Sendind key {} to device'.format(key))
        self._device.shell("input keyevent {}".format(key))

    def start_intent(self, uri):
        """Start an intent on the device."""
        _LOGGER.info('Starting activity with intent' + uri)
        out = self._device.shell(
            "am start -a android.intent.action.VIEW -d {}".format(uri))
        _LOGGER.info(out)

    def do_action(self, action):
        """Input the key corresponding to the action."""
        if action in ACTIONS:
            self._device.shell("input keyevent {}".format(ACTIONS[action]))
        else:
            _LOGGER.info('Unknown action "{}"'.format(action))
