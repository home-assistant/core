"""
Support to interface with the MPC-HC Web API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.mpchc/
"""
import logging
import re
import requests

from homeassistant.components.media_player import (
    MediaPlayerDevice)
from homeassistant.const import (
    STATE_OFF, STATE_IDLE, STATE_PAUSED, STATE_PLAYING)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the MPC-HC platform."""
    name = config.get("name", "MPC-HC")
    url = '{}:{}'.format(config.get('host'), config.get('port', '13579'))

    if config.get('host') is None:
        _LOGGER.error("Missing NPC-HC host address in config")
        return False

    add_devices([MpcHcDevice(name, url)])


# pylint: disable=abstract-method
class MpcHcDevice(MediaPlayerDevice):
    """Representation of a MPC-HC server."""

    def __init__(self, name, url):
        """Initialize the MPC-HC device."""
        self._name = name
        self._url = url

        self.update()

    def update(self):
        """Get the latest details."""
        self._player_variables = dict()

        try:
            response = requests.get("{}/variables.html".format(self._url),
                                    data=None, timeout=3)

            mpchc_variables = re.findall(r'<p id="(.+?)">(.+?)</p>', response.text)

            self._player_variables = dict()
            for var in mpchc_variables:
                self._player_variables[var[0]] = var[1].lower()
        except requests.exceptions.RequestException:
            _LOGGER.error("Could not connect to MPC-HC at: %s", self._url)

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
        elif state == 'paused':
            return STATE_PAUSED
        else:
            return STATE_IDLE

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._player_variables.get('file', None)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return int(self._player_variables.get('volumelevel', 0)) / 100.0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._player_variables.get('muted', '0') == '1'

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        duration = self._player_variables.get('durationstring',
                                              "00:00:00").split(':')

        return \
            int(duration[0]) * 3600 + \
            int(duration[1]) * 60 + \
            int(duration[2])
