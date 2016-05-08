"""
Support for Google Play Music Desktop Player.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.gpm_dp/
"""
import logging
import json

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_PAUSE, MediaPlayerDevice)
from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_OFF)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['websocket-client==0.35.0']
SUPPORT_GPMDP = SUPPORT_PAUSE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the GPMDP platform."""
    from websocket import create_connection

    name = config.get("name", "GPM Desktop Player")
    address = config.get("address")

    if address is None:
        _LOGGER.error("Missing address in config")
        return False

    add_devices([GPMDP(name, address, create_connection)])


class GPMDP(MediaPlayerDevice):
    """Representation of a GPMDP."""

    # pylint: disable=too-many-public-methods, abstract-method
    # pylint: disable=too-many-instance-attributes
    def __init__(self, name, address, create_connection):
        """Initialize."""
        self._connection = create_connection
        self._address = address
        self._name = name
        self._status = STATE_OFF
        self.update()

    def update(self):
        """Get the latest details from the player."""
        import socket
        try:
            self._ws = self._connection(("ws://" + self._address + ":5672"), timeout=1)
            state = self._ws.recv()
            if ((json.loads(state))['payload']) is True:
                self._ws.recv()
                self._ws.recv()
                song = self._ws.recv()
                self._title = ((json.loads(song))['payload']['title'])
                self._artist = ((json.loads(song))['payload']['artist'])
                self._albumart = ((json.loads(song))['payload']
                                  ['albumArt'])
                self._status = STATE_PLAYING
            elif ((json.loads(state))['payload']) is False:
                self._status = STATE_PAUSED
        except (socket.timeout, ConnectionRefusedError):
            self._status = STATE_OFF

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def state(self):
        """Return the state of the device."""
        return self._status

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._title

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self._artist

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._albumart

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_GPMDP

    def media_next_track(self):
        """Send media_next command to media player."""
        self._ws.send('{"namespace": "playback", "method": "forward"}')

    def media_previous_track(self):
        """Send media_previous command media player."""
        self._ws.send('{"namespace": "playback", "method": "rewind"}')

    def media_play(self):
        """Send media_play command to media player."""
        self._ws.send('{"namespace": "playback", "method": "playPause"}')
        self._status = STATE_PLAYING
        self.update_ha_state()

    def media_pause(self):
        """Send media_pause command to media player."""
        self._ws.send('{"namespace": "playback", "method": "playPause"}')
        self._status = STATE_PAUSED
        self.update_ha_state()
