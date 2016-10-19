"""
Support for Yamaha Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.yamaha/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, SUPPORT_PLAY_MEDIA,
    MEDIA_TYPE_MUSIC,
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, CONF_HOST, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['rxv==0.2.0']

_LOGGER = logging.getLogger(__name__)

SUPPORT_YAMAHA = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                 SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE | \
                 SUPPORT_PLAY_MEDIA

CONF_SOURCE_NAMES = 'source_names'
CONF_SOURCE_IGNORE = 'source_ignore'

DEFAULT_NAME = 'Yamaha Receiver'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_SOURCE_IGNORE, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_SOURCE_NAMES, default={}): {cv.string: cv.string},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Yamaha platform."""
    import rxv

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    source_ignore = config.get(CONF_SOURCE_IGNORE)
    source_names = config.get(CONF_SOURCE_NAMES)

    if host is None:
        receivers = []
        for recv in rxv.find():
            receivers.extend(recv.zone_controllers())
    else:
        ctrl_url = "http://{}:80/YamahaRemoteControl/ctrl".format(host)
        receivers = rxv.RXV(ctrl_url, name).zone_controllers()

    add_devices(
        YamahaDevice(name, receiver, source_ignore, source_names)
        for receiver in receivers)


class YamahaDevice(MediaPlayerDevice):
    """Representation of a Yamaha device."""

    # pylint: disable=too-many-public-methods, abstract-method
    # pylint: disable=too-many-instance-attributes
    def __init__(self, name, receiver, source_ignore, source_names):
        """Initialize the Yamaha Receiver."""
        self._receiver = receiver
        self._muted = False
        self._volume = 0
        self._pwstate = STATE_OFF
        self._current_source = None
        self._source_list = None
        self._source_ignore = source_ignore
        self._source_names = source_names
        self._reverse_mapping = None
        self.update()
        self._name = name
        self._zone = receiver.zone

    def update(self):
        """Get the latest details from the device."""
        if self._receiver.on:
            self._pwstate = STATE_ON
        else:
            self._pwstate = STATE_OFF
        self._muted = self._receiver.mute
        self._volume = (self._receiver.volume / 100) + 1

        if self.source_list is None:
            self.build_source_list()

        current_source = self._receiver.input
        self._current_source = self._source_names.get(
            current_source, current_source)

    def build_source_list(self):
        """Build the source list."""
        self._reverse_mapping = {alias: source for source, alias in
                                 self._source_names.items()}

        self._source_list = sorted(
            self._source_names.get(source, source) for source in
            self._receiver.inputs()
            if source not in self._source_ignore)

    @property
    def name(self):
        """Return the name of the device."""
        name = self._name
        if self._zone != "Main_Zone":
            # Zone will be one of Main_Zone, Zone_2, Zone_3
            name += " " + self._zone.replace('_', ' ')
        return name

    @property
    def state(self):
        """Return the state of the device."""
        return self._pwstate

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def source(self):
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_YAMAHA

    def turn_off(self):
        """Turn off media player."""
        self._receiver.on = False

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        receiver_vol = 100 - (volume * 100)
        negative_receiver_vol = -receiver_vol
        self._receiver.volume = negative_receiver_vol

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._receiver.mute = mute

    def turn_on(self):
        """Turn the media player on."""
        self._receiver.on = True
        self._volume = (self._receiver.volume / 100) + 1

    def select_source(self, source):
        """Select input source."""
        self._receiver.input = self._reverse_mapping.get(source, source)

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from an ID.

        This exposes a pass through for various input sources in the
        Yamaha to direct play certain kinds of media. media_type is
        treated as the input type that we are setting, and media id is
        specific to it.
        """
        if media_type == "NET RADIO":
            self._receiver.net_radio(media_id)

    @property
    def media_content_type(self):
        """Return the media content type."""
        if self.source == "NET RADIO":
            return MEDIA_TYPE_MUSIC

    @property
    def media_title(self):
        """Return the media title.

        This will vary by input source, as they provide different
        information in metadata.

        """
        if self.source == "NET RADIO":
            info = self._receiver.play_status()
            if info.song:
                return "%s: %s" % (info.station, info.song)
            else:
                return info.station
