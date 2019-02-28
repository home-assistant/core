"""Support for Enigma2 media players."""
import logging

import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.helpers.config_validation import (PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_TURN_ON,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    MEDIA_TYPE_TVSHOW)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, CONF_PORT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['openwebif.py==0.9']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Enigma2 Media Player'
DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 0

SUPPORTED_ENIGMA2 = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                          SUPPORT_TURN_OFF | SUPPORT_NEXT_TRACK | \
                          SUPPORT_PREVIOUS_TRACK | \
                          SUPPORT_TURN_ON | SUPPORT_PAUSE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of an enigma2 media player."""
    if discovery_info:
        discovered_config = {
            'name': DEFAULT_NAME,
            'port': DEFAULT_PORT,
            'host': discovery_info['host'],
            'timeout': DEFAULT_TIMEOUT,
        }
        add_devices([Enigma2Device(discovery_info['hostname'],
                                   discovered_config)], True)
        return

    # Generate a configuration for the Enigma2 library
    remote_config = {
        'name': 'HomeAssistant',
        'description': config[CONF_NAME],
        'port': config[CONF_PORT],
        'host': config[CONF_HOST],
        'timeout': DEFAULT_TIMEOUT,
    }

    add_devices([Enigma2Device(config[CONF_NAME], remote_config)], True)


class Enigma2Device(MediaPlayerDevice):
    """Representation of an Enigma2 box."""

    def __init__(self, name, config):
        """Initialize the Enigma2 device."""
        import openwebif.api
        self._state = None
        self._name = name
        self.e2_box = openwebif.api.CreateDevice(config['host'],
                                                 port=config['port'])

        self.volume = 10
        self.current_service_channel_name = None
        self.current_programme_name = None
        self.current_service_ref = None
        self.muted = False
        self.picon_url = None

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
        return SUPPORTED_ENIGMA2

    def turn_off(self):
        """Turn off media player."""
        self.e2_box.toggle_standby()

    def turn_on(self):
        """Turn the media player on."""
        self.e2_box.toggle_standby()

    @property
    def media_title(self):
        """Title of current playing media."""
        if self.current_service_ref.startswith('1:0:0'):
            return "[Recording Playback] - {}".format(
                self.current_programme_name)
        if self.current_service_channel_name:
            return "{} - {}".format(self.current_programme_name,
                                    self.current_service_channel_name)

        return self.current_programme_name

    @property
    def media_channel(self):
        """Channel of current playing media."""
        return self.current_service_channel_name

    @property
    def media_content_id(self):
        """Service Ref of current playing media."""
        return self.current_service_ref

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

    def volume_up(self):
        """Volume up the media player."""
        self.e2_box.set_volume(self.volume + 5)

    def volume_down(self):
        """Volume down media player."""
        self.e2_box.set_volume(self.volume - 5)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
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
        """Mute or unmute."""
        self.e2_box.mute_volume()

    def update(self):
        """Update state of the media_player."""
        status_info = self.e2_box.refresh_status_info()

        if self.e2_box.is_box_in_standby():
            self._state = STATE_OFF
            return
        self._state = STATE_ON
        self.current_service_channel_name = \
            status_info['currservice_station']
        pname = status_info['currservice_name']
        self.current_programme_name = pname if pname != "N/A" else ""
        self.current_service_ref = status_info['currservice_serviceref']
        self.muted = status_info['muted']
        self.volume = status_info['volume']
        self.picon_url = \
            self.e2_box.get_current_playing_picon_url(
                channel_name=self.current_service_channel_name,
                currservice_serviceref=self.current_service_ref)
