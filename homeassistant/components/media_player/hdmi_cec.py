"""
Support for Vera switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

from homeassistant.components.hdmi_cec import CecDevice, CEC_DEVICES, CEC_CLIENT
from homeassistant.components.media_player import MediaPlayerDevice

DEPENDENCIES = ['hdmi_cec']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and return Vera switches."""
    _LOGGER.info("setting CEC media players %s", CEC_DEVICES['media_player'])
    add_devices(
        CecMediaPlayer(hass, CEC_CLIENT, device) for
        device in CEC_DEVICES['media_player'])


class CecMediaPlayer(CecDevice, MediaPlayerDevice):
    """Representation of a Vera Switch."""

    def media_previous_track(self):
        pass

    def media_seek(self, position):
        pass

    def clear_playlist(self):
        pass

    def play_media(self, media_type, media_id):
        pass

    def media_play(self):
        pass

    def set_volume_level(self, volume):
        pass

    def mute_volume(self, mute):
        pass

    def media_next_track(self):
        pass

    def select_source(self, source):
        pass

    def media_pause(self):
        pass

    def media_stop(self):
        pass

    def __init__(self, hass, lib_cec, logical):
        """Initialize the Vera device."""
        self._state = False
        CecDevice.__init__(self, hass, lib_cec, logical)
