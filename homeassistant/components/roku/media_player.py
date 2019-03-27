"""Support for the Roku media player."""
import logging
import requests.exceptions

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MOVIE, SUPPORT_NEXT_TRACK, SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET)
from homeassistant.const import (CONF_HOST, STATE_HOME, STATE_IDLE,
                                 STATE_PLAYING)

DEPENDENCIES = ['roku']

DEFAULT_PORT = 8060

_LOGGER = logging.getLogger(__name__)

SUPPORT_ROKU = SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK |\
    SUPPORT_PLAY_MEDIA | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE |\
    SUPPORT_SELECT_SOURCE | SUPPORT_PLAY


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Roku platform."""
    if not discovery_info:
        return

    host = discovery_info[CONF_HOST]
    async_add_entities([RokuDevice(host)], True)


class RokuDevice(MediaPlayerDevice):
    """Representation of a Roku device on the network."""

    def __init__(self, host):
        """Initialize the Roku device."""
        from roku import Roku

        self.roku = Roku(host)
        self.ip_address = host
        self.channels = []
        self.current_app = None
        self._device_info = {}

    def update(self):
        """Retrieve latest state."""
        try:
            self._device_info = self.roku.device_info
            self.ip_address = self.roku.host
            self.channels = self.get_source_list()

            if self.roku.current_app is not None:
                self.current_app = self.roku.current_app
            else:
                self.current_app = None
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout):
            pass

    def get_source_list(self):
        """Get the list of applications to be used as sources."""
        return ["Home"] + sorted(channel.name for channel in self.roku.apps)

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def name(self):
        """Return the name of the device."""
        if self._device_info.userdevicename:
            return self._device_info.userdevicename
        return "Roku {}".format(self._device_info.sernum)

    @property
    def state(self):
        """Return the state of the device."""
        if self.current_app is None:
            return None

        if (self.current_app.name == "Power Saver" or
                self.current_app.is_screensaver):
            return STATE_IDLE
        if self.current_app.name == "Roku":
            return STATE_HOME
        if self.current_app.name is not None:
            return STATE_PLAYING

        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ROKU

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return self._device_info.sernum

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self.current_app is None:
            return None
        if self.current_app.name == "Power Saver":
            return None
        if self.current_app.name == "Roku":
            return None
        return MEDIA_TYPE_MOVIE

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.current_app is None:
            return None
        if self.current_app.name == "Roku":
            return None
        if self.current_app.name == "Power Saver":
            return None
        if self.current_app.id is None:
            return None

        return 'http://{0}:{1}/query/icon/{2}'.format(
            self.ip_address, DEFAULT_PORT, self.current_app.id)

    @property
    def app_name(self):
        """Name of the current running app."""
        if self.current_app is not None:
            return self.current_app.name

    @property
    def app_id(self):
        """Return the ID of the current running app."""
        if self.current_app is not None:
            return self.current_app.id

    @property
    def source(self):
        """Return the current input source."""
        if self.current_app is not None:
            return self.current_app.name

    @property
    def source_list(self):
        """List of available input sources."""
        return self.channels

    def media_play_pause(self):
        """Send play/pause command."""
        if self.current_app is not None:
            self.roku.play()

    def media_previous_track(self):
        """Send previous track command."""
        if self.current_app is not None:
            self.roku.reverse()

    def media_next_track(self):
        """Send next track command."""
        if self.current_app is not None:
            self.roku.forward()

    def mute_volume(self, mute):
        """Mute the volume."""
        if self.current_app is not None:
            self.roku.volume_mute()

    def volume_up(self):
        """Volume up media player."""
        if self.current_app is not None:
            self.roku.volume_up()

    def volume_down(self):
        """Volume down media player."""
        if self.current_app is not None:
            self.roku.volume_down()

    def select_source(self, source):
        """Select input source."""
        if self.current_app is not None:
            if source == "Home":
                self.roku.home()
            else:
                channel = self.roku[source]
                channel.launch()
