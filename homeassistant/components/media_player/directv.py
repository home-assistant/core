"""
Support for the DirecTV recievers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.directv/
"""
import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO, SUPPORT_PAUSE, SUPPORT_PLAY_MEDIA,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_STOP, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK, SUPPORT_PLAY,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_PLAYING, CONF_PORT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['directpy==0.1']

DEFAULT_NAME = 'DirecTV Receiver'
DEFAULT_PORT = 8080

SUPPORT_DTV = SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_NEXT_TRACK | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

KNOWN_HOSTS = []

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the DirecTV platform."""
    hosts = []

    if discovery_info:
        host = discovery_info.get('host')

        if host in KNOWN_HOSTS:
            return

        hosts.append([
            'DirecTV_' + discovery_info.get('serial', ''),
            host, DEFAULT_PORT
        ])

    elif CONF_HOST in config:
        hosts.append([
            config.get(CONF_NAME), config.get(CONF_HOST), config.get(CONF_PORT)
        ])

    dtvs = []

    for host in hosts:
        dtvs.append(DirecTvDevice(*host))
        KNOWN_HOSTS.append(host)

    add_devices(dtvs)

    return True


class DirecTvDevice(MediaPlayerDevice):
    """Representation of a DirecTV reciever on the network."""

    def __init__(self, name, host, port):
        """Initialize the device."""
        from DirectPy import DIRECTV
        self.dtv = DIRECTV(host, port)
        self._name = name
        self._is_standby = True
        self._current = None

    def update(self):
        """Retrieve latest state."""
        self._is_standby = self.dtv.get_standby()
        if self._is_standby:
            self._current = None
        else:
            self._current = self.dtv.get_tuned()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    # MediaPlayerDevice properties and methods
    @property
    def state(self):
        """Return the state of the device."""
        if self._is_standby:
            return STATE_OFF
        # Haven't determined a way to see if the content is paused
        else:
            return STATE_PLAYING

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        if self._is_standby:
            return None
        else:
            return self._current['programId']

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        if self._is_standby:
            return None
        else:
            return self._current['duration']

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self._is_standby:
            return None
        else:
            return self._current['title']

    @property
    def media_series_title(self):
        """Return the title of current episode of TV show."""
        if self._is_standby:
            return None
        else:
            if 'episodeTitle' in self._current:
                return self._current['episodeTitle']
            else:
                return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_DTV

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        if 'episodeTitle' in self._current:
            return MEDIA_TYPE_TVSHOW
        else:
            return MEDIA_TYPE_VIDEO

    @property
    def media_channel(self):
        """Return the channel current playing media."""
        if self._is_standby:
            return None
        else:
            chan = "{} ({})".format(
                self._current['callsign'], self._current['major'])
            return chan

    def turn_on(self):
        """Turn on the receiver."""
        self.dtv.key_press('poweron')

    def turn_off(self):
        """Turn off the receiver."""
        self.dtv.key_press('poweroff')

    def media_play(self):
        """Send play command."""
        self.dtv.key_press('play')

    def media_pause(self):
        """Send pause command."""
        self.dtv.key_press('pause')

    def media_stop(self):
        """Send stop command."""
        self.dtv.key_press('stop')

    def media_previous_track(self):
        """Send rewind command."""
        self.dtv.key_press('rew')

    def media_next_track(self):
        """Send fast forward command."""
        self.dtv.key_press('ffwd')
