"""
Support for the roku media player.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.roku/
"""

import logging

from homeassistant.components.media_player import (
    MEDIA_TYPE_VIDEO, SUPPORT_NEXT_TRACK, SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice)

from homeassistant.const import (
    CONF_HOST, STATE_IDLE, STATE_PLAYING, STATE_UNKNOWN, STATE_HOME)

REQUIREMENTS = [
    'https://github.com/bah2830/python-roku/archive/3.1.1.zip'
    '#python-roku==3.1.1']

KNOWN_HOSTS = []
DEFAULT_PORT = 8060

_LOGGER = logging.getLogger(__name__)

SUPPORT_ROKU = SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK |\
    SUPPORT_PLAY_MEDIA | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE |\
    SUPPORT_SELECT_SOURCE


# pylint: disable=abstract-method
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Roku platform."""
    hosts = []

    if discovery_info and discovery_info in KNOWN_HOSTS:
        return

    if discovery_info is not None:
        _LOGGER.debug('Discovered Roku: %s', discovery_info[0])
        hosts.append(discovery_info[0])

    elif CONF_HOST in config:
        hosts.append(config[CONF_HOST])

    rokus = []
    for host in hosts:
        rokus.append(RokuDevice(host))
        KNOWN_HOSTS.append(host)

    add_devices(rokus)


class RokuDevice(MediaPlayerDevice):
    """Representation of a Roku device on the network."""

    # pylint: disable=abstract-method
    # pylint: disable=too-many-public-methods
    def __init__(self, host):
        """Initialize the Roku device."""
        from roku import Roku

        self.roku = Roku(host)
        self.update()

    def update(self):
        """Retrieve latest state."""
        self.roku_name = "roku_" + self.roku.device_info.sernum
        self.ip_address = self.roku.host
        self.channels = self.get_source_list()

        if self.roku.current_app is not None:
            self.current_app = self.roku.current_app
        else:
            self.current_app = None

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
        return self.roku_name

    @property
    def state(self):
        """Return the state of the device."""
        if self.current_app.name in ["Power Saver", "Default screensaver"]:
            return STATE_IDLE
        elif self.current_app.name == "Roku":
            return STATE_HOME
        elif self.current_app.name is not None:
            return STATE_PLAYING

        return STATE_UNKNOWN

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_ROKU

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self.current_app is None:
            return None
        elif self.current_app.name == "Power Saver":
            return None
        elif self.current_app.name == "Roku":
            return None
        else:
            return MEDIA_TYPE_VIDEO

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.current_app is None:
            return None
        elif self.current_app.name == "Roku":
            return None
        elif self.current_app.name == "Power Saver":
            return None
        elif self.current_app.id is None:
            return None

        return 'http://{0}:{1}/query/icon/{2}'.format(self.ip_address,
                                                      DEFAULT_PORT,
                                                      self.current_app.id)

    @property
    def app_name(self):
        """Name of the current running app."""
        return self.current_app.name

    @property
    def app_id(self):
        """Return the ID of the current running app."""
        return self.current_app.id

    @property
    def source(self):
        """Return the current input source."""
        return self.current_app.name

    @property
    def source_list(self):
        """List of available input sources."""
        return self.channels

    def media_play_pause(self):
        """Send play/pause command."""
        self.roku.play()

    def media_previous_track(self):
        """Send previous track command."""
        self.roku.reverse()

    def media_next_track(self):
        """Send next track command."""
        self.roku.forward()

    def mute_volume(self, mute):
        """Mute the volume."""
        self.roku.volume_mute()

    def volume_up(self):
        """Volume up media player."""
        self.roku.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self.roku.volume_down()

    def select_source(self, source):
        """Select input source."""
        if source == "Home":
            self.roku.home()
        else:
            channel = self.roku[source]
            channel.launch()
