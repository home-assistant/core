"""
Support for Onkyo Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.onkyo/
"""
import logging

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice)
from homeassistant.const import STATE_OFF, STATE_ON

REQUIREMENTS = ['https://github.com/danieljkemp/onkyo-eiscp/archive/'
                'python3.zip#onkyo-eiscp==0.9.2']
_LOGGER = logging.getLogger(__name__)

SUPPORT_ONKYO = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Onkyo platform."""
    from eiscp import eISCP
    add_devices(OnkyoDevice(receiver)
                for receiver in eISCP.discover())


class OnkyoDevice(MediaPlayerDevice):
    """Representation of a Onkyo device."""

    # pylint: disable=too-many-public-methods, abstract-method
    def __init__(self, receiver):
        """Initialize the Onkyo Receiver."""
        self._receiver = receiver
        self._muted = False
        self._volume = 0
        self._pwstate = STATE_OFF
        self.update()
        self._name = '{}_{}'.format(
            receiver.info['model_name'], receiver.info['identifier'])
        self._current_source = None

    def update(self):
        """Get the latest details from the device."""
        status = self._receiver.command('system-power query')
        if status[1] == 'on':
            self._pwstate = STATE_ON
        else:
            self._pwstate = STATE_OFF
            return
        volume_raw = self._receiver.command('volume query')
        mute_raw = self._receiver.command('audio-muting query')
        current_source_raw = self._receiver.command('input-selector query')
        self._current_source = '_'.join('_'.join(
            [i for i in current_source_raw[1]]))
        self._muted = bool(mute_raw[1] == 'on')
        self._volume = int(volume_raw[1], 16)/80.0

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
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_ONKYO

    @property
    def source(self):
        """"Return the current input source of the device."""
        return self._current_source

    def turn_off(self):
        """Turn off media player."""
        self._receiver.command('system-power standby')

    def set_volume_level(self, volume):
        """Set volume level, input is range 0..1. Onkyo ranges from 1-80."""
        self._receiver.command('volume {}'.format(int(volume*80)))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self._receiver.command('audio-muting on')
        else:
            self._receiver.command('audio-muting off')

    def turn_on(self):
        """Turn the media player on."""
        self._receiver.power_on()

    def select_source(self, source):
        """Set the input source."""
        self._receiver.command('input-selector {}'.format(source))
