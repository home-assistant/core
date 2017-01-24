"""
Support for interface with an Orange Livebox Play TV appliance.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.liveboxplaytv/
"""
import logging
from datetime import timedelta
from urllib.parse import urlparse

import voluptuous as vol

import homeassistant.util as util
from homeassistant.components.media_player import (
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_PLAY,
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_VOLUME_STEP, SUPPORT_VOLUME_MUTE, SUPPORT_SELECT_SOURCE,
    MEDIA_TYPE_CHANNEL, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, STATE_ON, STATE_OFF, STATE_PLAYING,
    STATE_PAUSED, STATE_UNKNOWN, CONF_NAME)
from homeassistant.loader import get_component
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'https://github.com/pschmitt/python-liveboxplaytv/archive/1.1.0.zip'
    '#liveboxplaytv==1.1.0']

_CONFIGURING = {}  # type: Dict[str, str]
_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Livebox Play TV'
DEFAULT_PORT = 8080

SUPPORT_LIVEBOXPLAYTV = SUPPORT_TURN_OFF | SUPPORT_TURN_ON | \
    SUPPORT_NEXT_TRACK | SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | \
    SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | SUPPORT_SELECT_SOURCE | \
    SUPPORT_PLAY

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Orange Livebox Play TV platform."""
    if discovery_info is not None:
        host = urlparse(discovery_info[1]).hostname
        port = urlparse(discovery_info[1]).port
    else:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)

    if host is None:
        _LOGGER.error("No Orange Livebox TV found in configuration file "
                      "or with discovery")
        return False

    # Only act if we are not already configuring this host
    if host in _CONFIGURING:
        return

    setup_liveboxplaytv(host, port, name, hass, add_devices)


def setup_liveboxplaytv(host, port, name, hass, add_devices):
    """Setup an Orange Livebox Play TV based on host parameter."""
    add_devices([LiveboxPlayTvDevice(host, port, name)], True)


def request_configuration(host, port, name, hass, add_devices):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], 'Failed to set up, please try again.')
        return


class LiveboxPlayTvDevice(MediaPlayerDevice):
    """Representation of an Orange Livebox Play TV."""

    def __init__(self, host, port, name):
        """Initialize the Livebox Play TV device."""
        from liveboxplaytv import LiveboxPlayTv
        self._client = LiveboxPlayTv(host, port)
        # Assume that the appliance is not muted
        self._muted = False
        # Assume that the TV is in Play mode
        self._name = name
        self._playing = True
        self._volume = 0
        self._current_source = None
        self._state = STATE_UNKNOWN
        self._channel_list = {}
        self._current_channel = None
        self._media_image_url = None

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve the latest data."""
        import requests
        try:
            self._state = STATE_PLAYING if self._client.is_on else STATE_OFF
            # TODO
            self._muted = False
            self._volume = 100  # self._client.get_volume()

            # Update current channel
            channel = self._client.get_current_channel()
            self._current_channel = channel['name']
            self._media_image_url = channel['imageUrl']
            self.refresh_channel_list()
        except requests.ConnectionError:
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
        return self._current_channel

    @property
    def source_list(self):
        """List of available input sources."""
        # Sort channels by tvIndex
        return [self._channel_list[c] for c in
                sorted(self._channel_list.keys())]

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        # return self._client.media_type
        return MEDIA_TYPE_CHANNEL

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._media_image_url

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_LIVEBOXPLAYTV

    def refresh_channel_list(self):
        """Refresh the list of available channels."""
        new_channel_list = {}
        # update channels
        for channel in self._client.get_channels():
            new_channel_list[int(channel['tvIndex'])] = channel['name']
        self._channel_list = new_channel_list

    def turn_off(self):
        """Turn off media player."""
        self._state = STATE_OFF
        self._client.turn_off()

    def turn_on(self):
        """Turn on the media player."""
        self._state = STATE_ON
        self._client.turn_on()

    def volume_up(self):
        """Volume up the media player."""
        self._client.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._client.volume_down()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        # TODO
        pass

    def mute_volume(self, mute):
        """Send mute command."""
        self._muted = mute
        self._client.mute()

    def media_play_pause(self):
        """Simulate play pause media player."""
        self._client.play_pause()

    def select_source(self, source):
        """Select input source."""
        self._current_source = source
        self._client.set_channel(source)

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._state = STATE_PLAYING
        self._client.play()

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._state = STATE_PAUSED
        self._client.pause()

    def media_next_track(self):
        """Send next track command."""
        self._client.channel_up()

    def media_previous_track(self):
        """Send the previous track command."""
        self._client.channel_down()
