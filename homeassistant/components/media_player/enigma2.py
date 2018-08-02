"""
Support for Enigma2 based media players.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.enigma2/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_TURN_ON,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MediaPlayerDevice, PLATFORM_SCHEMA, MEDIA_TYPE_TVSHOW)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN, CONF_PORT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['openwebif.py==0.9']

_LOGGER = logging.getLogger(__name__)

CONF_TIMEOUT = 'timeout'

DEFAULT_NAME = 'Enigma2 Media Player'
DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 0

# Support different items when watching recording playback
SUPPORT_ENIGMA2_RECORDING_PLAYBACK = SUPPORT_VOLUME_SET | \
                                     SUPPORT_VOLUME_MUTE | \
                                     SUPPORT_TURN_OFF | SUPPORT_PAUSE

SUPPORT_ENIGMA2_LIVE_TV = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                          SUPPORT_TURN_OFF | SUPPORT_NEXT_TRACK | \
                          SUPPORT_PREVIOUS_TRACK | SUPPORT_TURN_ON

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Enigma2 TV platform."""
    name = config.get(CONF_NAME)

    # Generate a configuration for the Enigma2 library
    remote_config = {
        'name': 'HomeAssistant',
        'description': config.get(CONF_NAME),
        'port': config.get(CONF_PORT),
        'host': config.get(CONF_HOST),
        'timeout': config.get(CONF_TIMEOUT),
    }

    add_devices([Enigma2Device(name, remote_config)])


# pylint: disable=abstract-method
class Enigma2Device(MediaPlayerDevice):
    """Representation of a Enigma2 box."""

    # pylint: disable=too-many-public-methods
    def __init__(self, name, config):
        """Initialize the Enigma2 device."""
        import openwebif.api
        self._state = STATE_UNKNOWN
        # self.config = config

        self._name = name
        self.e2_box = openwebif.api.CreateDevice(config['host'],
                                                 port=config['port'])

        self.volume = 20
        self.current_service_channel_name = None
        self.current_programme_name = None
        self.currservice_serviceref = None
        self.muted = False
        self.picon_url = None

        self.update()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        from openwebif.api import PlaybackType

        if self.e2_box.get_current_playback_type(
                self.currservice_serviceref) == PlaybackType.recording:
            return SUPPORT_ENIGMA2_RECORDING_PLAYBACK

        return SUPPORT_ENIGMA2_LIVE_TV

    def turn_off(self):
        """Turn off media player."""
        if self.state is STATE_ON:
            self.e2_box.toggle_standby()

    def turn_on(self):
        """Turn the media player on."""
        if self.state is STATE_OFF:
            self.e2_box.toggle_standby()
            self.update()

    @property
    def media_title(self):
        """Title of current playing media."""
        if self.currservice_serviceref.startswith('1:0:0'):
            return "[Recording Playback] - " + \
                   self.current_programme_name
        if self.current_service_channel_name:
            return self.current_programme_name + " - " + \
                   self.current_service_channel_name

        return self.current_programme_name

    @property
    def media_channel(self):
        """Channel of current playing media."""
        return self.current_service_channel_name

    @property
    def media_content_id(self):
        """Service Ref of current playing media."""
        return self.currservice_serviceref

    @property
    def media_content_type(self):
        """Type of video currently playing."""
        return MEDIA_TYPE_TVSHOW

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.muted

    @property
    def media_image_url(self):
        """Picon url for the channel."""
        return self.picon_url

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.e2_box.set_volume(int(volume * 100))
        self.volume = volume * 100

    def volume_up(self):
        """Volume up the media player."""
        self.volume += 5
        self.e2_box.set_volume(self.volume)

    def volume_down(self):
        """Volume down media player."""
        self.volume -= 5
        self.e2_box.set_volume(self.volume)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        _LOGGER.info('self.volume : %s', self.volume)
        return self.volume / 100

    def media_play_pause(self):
        """Pause media on media player."""
        self.e2_box.toggle_play_pause()

    def media_play(self):
        """Play media."""
        self.e2_box.toggle_play_pause()

    def media_pause(self):
        """Pause the media player."""
        self.e2_box.toggle_play_pause()

    def media_next_track(self):
        """Send next track command."""
        self.e2_box.set_channel_up()

    def media_previous_track(self):
        """Send next track command."""
        self.e2_box.set_channel_down()

    def mute_volume(self, mute):
        """Send mute command."""
        self.e2_box.mute_volume()

    def update(self):
        """Update state of the media_player."""
        _LOGGER.info("Updating...")
        status_info = self.e2_box.refresh_status_info()

        if self.e2_box.is_box_in_standby():
            self._state = STATE_OFF
        else:
            self._state = STATE_ON
            self.current_service_channel_name = \
                status_info['currservice_station']
            pname = status_info['currservice_name']
            self.current_programme_name = pname if pname != "N/A" else ""
            self.currservice_serviceref = status_info['currservice_serviceref']
            self.muted = status_info['muted']
            self.volume = status_info['volume']
            self.picon_url = \
                self.e2_box.get_current_playing_picon_url(
                    channel_name=self.current_service_channel_name,
                    currservice_serviceref=self.currservice_serviceref)
