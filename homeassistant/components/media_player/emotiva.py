"""
Support for Emotiva Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.emotiva/
"""
import logging

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE, MediaPlayerDevice)
from homeassistant.const import STATE_OFF, STATE_ON

REQUIREMENTS = ["https://github.com/thecynic/pymotiva/archive/"
                "v0.1.0.zip#pymotiva==0.1.0"]

_LOGGER = logging.getLogger(__name__)

SUPPORT_EMOTIVA = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Emotiva platform."""
    from pymotiva import Emotiva

    add_devices(EmotivaDevice(Emotiva(ip, info))
                for ip, info in Emotiva.discover())


class EmotivaDevice(MediaPlayerDevice):
    """Representation of an Emotiva device."""

    # pylint: disable=too-many-public-methods, abstract-method
    # pylint: disable=too-many-instance-attributes
    def __init__(self, emo):
        """Initialize the Emotiva Receiver."""
        self._emo = emo
        self._emo.connect()
        self._name = '%s %s' % (self._emo.name, self._emo.model)
        self._min_volume = -96.0
        self._max_volume = 11

        self.update()
        self._emo.set_update_cb(lambda: self.update_ha_state())

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return {True: STATE_ON, False: STATE_OFF}[self._emo.power]

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return ((self._emo.volume - self._min_volume) /
                (self._max_volume - self._min_volume))

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._emo.mute

    @property
    def source(self):
        """Return the current input source."""
        return self._emo.source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._emo.sources

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_EMOTIVA

    def turn_off(self):
        """Turn off media player."""
        self._emo.power = False

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._emo.mute = mute

    def volume_up(self):
        self._emo.volume_up()

    def volume_down(self):
        self._emo.volume_down()

    def turn_on(self):
        """Turn the media player on."""
        self._emo.power = True

    def select_source(self, source):
        """Select input source."""
        self._emo.source = source
