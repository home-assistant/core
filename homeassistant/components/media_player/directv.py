"""
Support for the DirecTV receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.directv/
"""
import voluptuous as vol
import requests

from homeassistant.components.media_player import (
    MEDIA_TYPE_TVSHOW, MEDIA_TYPE_VIDEO, SUPPORT_PAUSE, SUPPORT_PLAY_MEDIA,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_STOP, PLATFORM_SCHEMA,
    SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK, SUPPORT_PLAY,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_NAME, STATE_OFF, STATE_PLAYING, CONF_PORT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['directpy==0.2']

DEFAULT_DEVICE = '0'
DEFAULT_NAME = 'DirecTV Receiver'
DEFAULT_PORT = 8080

SUPPORT_DTV = SUPPORT_PAUSE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP | SUPPORT_NEXT_TRACK | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_PLAY

DATA_DIRECTV = "data_directv"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the DirecTV platform."""
    known_devices = hass.data.get(DATA_DIRECTV)
    if not known_devices:
        known_devices = []
    hosts = []

    if CONF_HOST in config:
        hosts.append([
            config.get(CONF_NAME), config.get(CONF_HOST),
            config.get(CONF_PORT), config.get(CONF_DEVICE)
        ])

    elif discovery_info:
        host = discovery_info.get('host')
        name = 'DirecTV_' + discovery_info.get('serial', '')

        # attempt to discover additional RVU units
        try:
            resp = requests.get(
                'http://%s:%d/info/getLocations' % (host, DEFAULT_PORT)).json()
            if "locations" in resp:
                for loc in resp["locations"]:
                    if("locationName" in loc and "clientAddr" in loc
                       and loc["clientAddr"] not in known_devices):
                        hosts.append([str.title(loc["locationName"]), host,
                                      DEFAULT_PORT, loc["clientAddr"]])

        except requests.exceptions.RequestException:
            # bail out and just go forward with uPnP data
            if DEFAULT_DEVICE not in known_devices:
                hosts.append([name, host, DEFAULT_PORT, DEFAULT_DEVICE])

    dtvs = []

    for host in hosts:
        dtvs.append(DirecTvDevice(*host))
        known_devices.append(host[-1])

    add_devices(dtvs)
    hass.data[DATA_DIRECTV] = known_devices

    return True


class DirecTvDevice(MediaPlayerDevice):
    """Representation of a DirecTV receiver on the network."""

    def __init__(self, name, host, port, device):
        """Initialize the device."""
        from DirectPy import DIRECTV
        self.dtv = DIRECTV(host, port, device)
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
        return STATE_PLAYING

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        if self._is_standby:
            return None
        return self._current['programId']

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        if self._is_standby:
            return None
        return self._current['duration']

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self._is_standby:
            return None
        return self._current['title']

    @property
    def media_series_title(self):
        """Return the title of current episode of TV show."""
        if self._is_standby:
            return None
        elif 'episodeTitle' in self._current:
            return self._current['episodeTitle']
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
        return MEDIA_TYPE_VIDEO

    @property
    def media_channel(self):
        """Return the channel current playing media."""
        if self._is_standby:
            return None

        return "{} ({})".format(
            self._current['callsign'], self._current['major'])

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
