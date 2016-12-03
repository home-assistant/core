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

    def __init__(self, hass, cec_client, logical):
        """Initialize the Vera device."""
        self._state = False
        CecDevice.__init__(self, hass, cec_client, logical)
