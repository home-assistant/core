"""
Support for interacting with Snapcast clients.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.snapcast/
"""

import logging
import socket

from homeassistant.components.media_player import (
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import STATE_OFF, STATE_ON

SUPPORT_SNAPCAST = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE
DOMAIN = 'snapcast'
REQUIREMENTS = ['snapcast==1.1.1']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Snapcast platform."""
    import snapcast.control
    host = config.get('host')
    port = config.get('port', snapcast.control.CONTROL_PORT)
    if not host:
        _LOGGER.error('No snapserver host specified')
        return
    try:
        server = snapcast.control.Snapserver(host, port)
    except socket.gaierror:
        _LOGGER.error('Could not connect to Snapcast server at %s:%d',
                      host, port)
        return
    add_devices([SnapcastDevice(client) for client in server.clients])


class SnapcastDevice(MediaPlayerDevice):
    """Representation of a Snapcast client device."""

    # pylint: disable=abstract-method
    def __init__(self, client):
        """Initialize the Snapcast device."""
        self._client = client

    @property
    def name(self):
        """Return the name of the device."""
        return self._client.identifier

    @property
    def volume_level(self):
        """Return the volume level."""
        return self._client.volume / 100

    @property
    def is_volume_muted(self):
        """Volume muted."""
        return self._client.muted

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_SNAPCAST

    @property
    def state(self):
        """Return the state of the player."""
        if self._client.connected:
            return STATE_ON
        return STATE_OFF

    def mute_volume(self, mute):
        """Send the mute command."""
        self._client.muted = mute

    def set_volume_level(self, volume):
        """Set the volume level."""
        self._client.volume = round(volume * 100)
