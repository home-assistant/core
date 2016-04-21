"""
Support for Yamaha Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.yamaha/
"""
import logging

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice)
from homeassistant.const import STATE_OFF, STATE_ON

REQUIREMENTS = ['rxv==0.1.11']

_LOGGER = logging.getLogger(__name__)

SUPPORT_YAMAHA = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Yamaha platform."""
    import rxv

    excludes = config.get('excludes', None)
    mapping = config.get('mapping', None)

    add_devices(YamahaDevice(config.get("name"), receiver, excludes, mapping)
                for receiver in rxv.find())


class YamahaDevice(MediaPlayerDevice):
    """Representation of a Yamaha device."""

    # pylint: disable=too-many-public-methods, abstract-method
    # pylint: disable=too-many-instance-attributes
    def __init__(self, name, receiver, excludes=None, mapping=None):
        """Initialize the Yamaha Receiver."""
        self._receiver = receiver
        self._muted = False
        self._volume = 0
        self._pwstate = STATE_OFF
        self._current_source = None
        self._source_list = None
        self._excludes = excludes
        self._mapping = mapping
        self._reverse_mapping = None
        self.update()
        self._name = name

    def update(self):
        """Get the latest details from the device."""
        if self._receiver.on:
            self._pwstate = STATE_ON
        else:
            self._pwstate = STATE_OFF
        self._muted = self._receiver.mute
        self._volume = (self._receiver.volume/100) + 1

        if self.source_list is None:
            self.build_source_list()

        current_source = self._receiver.input
        if self._mapping is not None:
            if current_source in list(self._mapping.keys()):
                self._current_source = self._mapping[current_source]
            else:
                self._current_source = current_source
        else:
            self._current_source = current_source

    def build_source_list(self):
        """Build the source list."""
        self._source_list = []

        if self._mapping is not None:
            self._reverse_mapping = {}
            mapping_list = list(self._mapping.keys())
            for source, alias in self._mapping.items():
                self._reverse_mapping[alias] = source
        else:
            mapping_list = []

        source_list = list(self._receiver.inputs().keys())
        for source in source_list:
            if self._excludes is not None and source in self._excludes:
                continue
            if source in mapping_list:
                self._source_list.append(self._mapping[source])
            else:
                self._source_list.append(source)
        self._source_list.sort()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

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
        receiver_vol = 100-(volume * 100)
        negative_receiver_vol = -receiver_vol
        self._receiver.volume = negative_receiver_vol

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._receiver.mute = mute

    def turn_on(self):
        """Turn the media player on."""
        self._receiver.on = True
        self._volume = (self._receiver.volume/100) + 1

    def select_source(self, source):
        """Select input source."""
        if self._reverse_mapping is not None:
            if source in list(self._reverse_mapping.keys()):
                self._receiver.input = self._reverse_mapping[source]
            else:
                self._receiver.input = source
        else:
            self._receiver.input = source
