"""
Support for LG TV running on NetCast 3 or 4.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.lg_netcast/
"""
from datetime import timedelta
import logging

from requests import RequestException
import voluptuous as vol

from homeassistant import util
from homeassistant.components.media_player import (
    MEDIA_TYPE_CHANNEL, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_ACCESS_TOKEN, CONF_HOST, CONF_NAME, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pylgnetcast-homeassistant==0.2.0.dev0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'LG TV Remote'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SUPPORT_LGTV = SUPPORT_PAUSE | SUPPORT_VOLUME_STEP | \
               SUPPORT_VOLUME_MUTE | SUPPORT_PREVIOUS_TRACK | \
               SUPPORT_NEXT_TRACK | SUPPORT_TURN_OFF | \
               SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_ACCESS_TOKEN): vol.All(cv.string, vol.Length(max=6)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the LG TV platform."""
    from pylgnetcast import LgNetCastClient

    host = config.get(CONF_HOST)
    access_token = config.get(CONF_ACCESS_TOKEN)
    name = config.get(CONF_NAME)

    client = LgNetCastClient(host, access_token)

    add_entities([LgTVDevice(client, name)], True)


class LgTVDevice(MediaPlayerDevice):
    """Representation of a LG TV."""

    def __init__(self, client, name):
        """Initialize the LG TV device."""
        self._client = client
        self._name = name
        self._muted = False
        # Assume that the TV is in Play mode
        self._playing = True
        self._volume = 0
        self._channel_name = ''
        self._program_name = ''
        self._state = STATE_UNKNOWN
        self._sources = {}
        self._source_names = []

    def send_command(self, command):
        """Send remote control commands to the TV."""
        from pylgnetcast import LgNetCastError
        try:
            with self._client as client:
                client.send_command(command)
        except (LgNetCastError, RequestException):
            self._state = STATE_OFF

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve the latest data from the LG TV."""
        from pylgnetcast import LgNetCastError
        try:
            with self._client as client:
                self._state = STATE_PLAYING
                volume_info = client.query_data('volume_info')
                if volume_info:
                    volume_info = volume_info[0]
                    self._volume = float(volume_info.find('level').text)
                    self._muted = volume_info.find('mute').text == 'true'

                channel_info = client.query_data('cur_channel')
                if channel_info:
                    channel_info = channel_info[0]
                    self._channel_name = channel_info.find('chname').text
                    self._program_name = channel_info.find('progName').text

                channel_list = client.query_data('channel_list')
                if channel_list:
                    channel_names = []
                    for channel in channel_list:
                        channel_name = channel.find('chname')
                        if channel_name is not None:
                            channel_names.append(str(channel_name.text))
                    self._sources = dict(zip(channel_names, channel_list))
                    # sort source names by the major channel number
                    source_tuples = [(k, self._sources[k].find('major').text)
                                     for k in self._sources]
                    sorted_sources = sorted(
                        source_tuples, key=lambda channel: int(channel[1]))
                    self._source_names = [n for n, k in sorted_sources]
        except (LgNetCastError, RequestException):
            self._state = STATE_OFF

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
        """Volume level of the media player (0..1)."""
        return self._volume / 100.0

    @property
    def source(self):
        """Return the current input source."""
        return self._channel_name

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_CHANNEL

    @property
    def media_channel(self):
        """Channel currently playing."""
        return self._channel_name

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._program_name

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_LGTV

    @property
    def media_image_url(self):
        """URL for obtaining a screen capture."""
        return self._client.url + 'data?target=screen_image'

    def turn_off(self):
        """Turn off media player."""
        self.send_command(1)

    def volume_up(self):
        """Volume up the media player."""
        self.send_command(24)

    def volume_down(self):
        """Volume down media player."""
        self.send_command(25)

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_command(26)

    def select_source(self, source):
        """Select input source."""
        self._client.change_channel(self._sources[source])

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._state = STATE_PLAYING
        self.send_command(33)

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._state = STATE_PAUSED
        self.send_command(34)

    def media_next_track(self):
        """Send next track command."""
        self.send_command(36)

    def media_previous_track(self):
        """Send the previous track command."""
        self.send_command(37)
