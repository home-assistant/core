"""Support for Enigma2 media players."""
import logging
import asyncio
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.helpers.config_validation import (PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_TURN_ON,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_STOP,
    SUPPORT_SELECT_SOURCE, SUPPORT_VOLUME_STEP, MEDIA_TYPE_TVSHOW)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_SSL,
    STATE_OFF, STATE_ON, STATE_PLAYING, CONF_PORT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['openwebifpy==1.2.4']

_LOGGER = logging.getLogger(__name__)

ATTR_MEDIA_CURRENTLY_RECORDING = 'media_currently_recording'
ATTR_MEDIA_DESCRIPTION = 'media_description'
ATTR_MEDIA_END_TIME = 'media_end_time'
ATTR_MEDIA_START_TIME = 'media_start_time'

CONF_PREFER_PICON = "prefer_picon"

DEFAULT_NAME = 'Enigma2 Media Player'
DEFAULT_PORT = 80
DEFAULT_SSL = False
DEFAULT_PREFER_PICON = False
DEFAULT_USERNAME = 'root'
DEFAULT_PASSWORD = 'dreambox'

SUPPORTED_ENIGMA2 = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                    SUPPORT_TURN_OFF | SUPPORT_NEXT_TRACK | SUPPORT_STOP | \
                    SUPPORT_PREVIOUS_TRACK | SUPPORT_VOLUME_STEP | \
                    SUPPORT_TURN_ON | SUPPORT_PAUSE | SUPPORT_SELECT_SOURCE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_PREFER_PICON, default=DEFAULT_PREFER_PICON): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of an enigma2 media player."""
    if discovery_info:
        discovered_config = {
            CONF_NAME: DEFAULT_NAME,
            # Do not use the discovered port, as it is the streaming
            # service port (8001) which is not what we want.
            CONF_PORT: DEFAULT_PORT,
            CONF_HOST: discovery_info['host'],
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: DEFAULT_PASSWORD,
            CONF_SSL: DEFAULT_SSL,
            CONF_PREFER_PICON: DEFAULT_PREFER_PICON,
        }
        add_devices([Enigma2Device(discovery_info['hostname'],
                                   discovered_config)], True)
        return

    add_devices([Enigma2Device(config[CONF_NAME], config)], True)


class Enigma2Device(MediaPlayerDevice):
    """Representation of an Enigma2 box."""

    def __init__(self, name, config):
        """Initialize the Enigma2 device."""
        import openwebif.api
        self._name = name
        self.e2_box = \
            openwebif.api.CreateDevice(host=config[CONF_HOST],
                                       port=config[CONF_PORT],
                                       username=config[CONF_USERNAME],
                                       password=config[CONF_PASSWORD],
                                       is_https=config[CONF_SSL],
                                       prefer_picon=config[CONF_PREFER_PICON])

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self.e2_box.is_recording_playback:
            return STATE_PLAYING
        return STATE_OFF if self.e2_box.in_standby else STATE_ON

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORTED_ENIGMA2

    def turn_off(self):
        """Turn off media player."""
        self.e2_box.turn_off()

    def turn_on(self):
        """Turn the media player on."""
        self.e2_box.turn_on()

    @property
    def media_title(self):
        """Title of current playing media."""
        return self.e2_box.current_service_channel_name

    @property
    def media_series_title(self):
        """Return the title of current episode of TV show."""
        return self.e2_box.current_programme_name

    @property
    def media_channel(self):
        """Channel of current playing media."""
        return self.e2_box.current_service_channel_name

    @property
    def media_content_id(self):
        """Service Ref of current playing media."""
        return self.e2_box.current_service_ref

    @property
    def media_content_type(self):
        """Type of video currently playing."""
        return MEDIA_TYPE_TVSHOW

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.e2_box.muted

    @property
    def media_image_url(self):
        """Picon url for the channel."""
        return self.e2_box.picon_url

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.e2_box.set_volume(int(volume * 100))

    def volume_up(self):
        """Volume up the media player."""
        self.e2_box.set_volume(self.e2_box.volume + 5)

    def volume_down(self):
        """Volume down media player."""
        self.e2_box.set_volume(self.e2_box.volume - 5)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self.e2_box.volume

    def media_stop(self):
        """Send stop command."""
        self.e2_box.set_stop()

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

    @property
    def source(self):
        """Return the current input source."""
        return self.e2_box.current_service_channel_name

    @property
    def source_list(self):
        """List of available input sources."""
        return self.e2_box.source_list

    @asyncio.coroutine
    def async_select_source(self, source):
        """Select input source."""
        self.e2_box.select_source(self.e2_box.sources[source])

    def update(self):
        """Update state of the media_player."""
        self.e2_box.update()

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if not self.e2_box.in_standby:
            attributes[ATTR_MEDIA_CURRENTLY_RECORDING] = \
                self.e2_box.status_info['isRecording']
            attributes[ATTR_MEDIA_DESCRIPTION] = \
                self.e2_box.status_info['currservice_fulldescription']
            attributes[ATTR_MEDIA_START_TIME] = \
                self.e2_box.status_info['currservice_begin']
            attributes[ATTR_MEDIA_END_TIME] = \
                self.e2_box.status_info['currservice_end']

        return attributes
