"""
Support to interface with the MPC-HC Web API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.mpchc/
"""
import logging
import re

import requests
import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_VOLUME_MUTE, SUPPORT_PAUSE, SUPPORT_STOP, SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_VOLUME_STEP, SUPPORT_PLAY,
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    STATE_OFF, STATE_IDLE, STATE_PAUSED, STATE_PLAYING, CONF_NAME, CONF_HOST,
    CONF_PORT)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'MPC-HC'
DEFAULT_PORT = 13579

SUPPORT_MPCHC = SUPPORT_VOLUME_MUTE | SUPPORT_PAUSE | SUPPORT_STOP | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_VOLUME_STEP | \
    SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MPC-HC platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    url = '{}:{}'.format(host, port)

    add_devices([MpcHcDevice(name, url)], True)


class MpcHcDevice(MediaPlayerDevice):
    """Representation of a MPC-HC server."""

    def __init__(self, name, url):
        """Initialize the MPC-HC device."""
        self._name = name
        self._url = url
        self._player_variables = dict()

    def update(self):
        """Get the latest details."""
        try:
            response = requests.get(
                '{}/variables.html'.format(self._url), data=None, timeout=3)

            mpchc_variables = re.findall(
                r'<p id="(.+?)">(.+?)</p>', response.text)

            for var in mpchc_variables:
                self._player_variables[var[0]] = var[1].lower()
        except requests.exceptions.RequestException:
            _LOGGER.error("Could not connect to MPC-HC at: %s", self._url)

    def _send_command(self, command_id):
        """Send a command to MPC-HC via its window message ID."""
        try:
            params = {"wm_command": command_id}
            requests.get("{}/command.html".format(self._url),
                         params=params, timeout=3)
        except requests.exceptions.RequestException:
            _LOGGER.error("Could not send command %d to MPC-HC at: %s",
                          command_id, self._url)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        state = self._player_variables.get('statestring', None)

        if state is None:
            return STATE_OFF
        if state == 'playing':
            return STATE_PLAYING
        if state == 'paused':
            return STATE_PAUSED

        return STATE_IDLE

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self._player_variables.get('file', None)

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return int(self._player_variables.get('volumelevel', 0)) / 100.0

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._player_variables.get('muted', '0') == '1'

    @property
    def media_duration(self):
        """Return the duration of the current playing media in seconds."""
        duration = self._player_variables.get(
            'durationstring', "00:00:00").split(':')
        return \
            int(duration[0]) * 3600 + \
            int(duration[1]) * 60 + \
            int(duration[2])

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_MPCHC

    def volume_up(self):
        """Volume up the media player."""
        self._send_command(907)

    def volume_down(self):
        """Volume down media player."""
        self._send_command(908)

    def mute_volume(self, mute):
        """Mute the volume."""
        self._send_command(909)

    def media_play(self):
        """Send play command."""
        self._send_command(887)

    def media_pause(self):
        """Send pause command."""
        self._send_command(888)

    def media_stop(self):
        """Send stop command."""
        self._send_command(890)

    def media_next_track(self):
        """Send next track command."""
        self._send_command(920)

    def media_previous_track(self):
        """Send previous track command."""
        self._send_command(919)
