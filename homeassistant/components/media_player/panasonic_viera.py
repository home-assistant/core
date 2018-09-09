"""
Support for interface with a Panasonic Viera TV.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.panasonic_viera/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_URL, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PLAY, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_MAC, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON,
    STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['panasonic_viera==0.3.1', 'wakeonlan==1.0.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Panasonic Viera TV'
DEFAULT_PORT = 55000

SUPPORT_VIERATV = SUPPORT_PAUSE | SUPPORT_VOLUME_STEP | \
    SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_TURN_OFF | SUPPORT_PLAY | \
    SUPPORT_PLAY_MEDIA | SUPPORT_STOP

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Panasonic Viera TV platform."""
    from panasonic_viera import RemoteControl

    mac = config.get(CONF_MAC)
    name = config.get(CONF_NAME)
    port = config.get(CONF_PORT)

    if discovery_info:
        _LOGGER.debug('%s', discovery_info)
        name = discovery_info.get('name')
        host = discovery_info.get('host')
        port = discovery_info.get('port')
        udn = discovery_info.get('udn')
        if udn and udn.startswith('uuid:'):
            uuid = udn[len('uuid:'):]
        else:
            uuid = None
        remote = RemoteControl(host, port)
        add_entities([PanasonicVieraTVDevice(mac, name, remote, uuid)])
        return True

    host = config.get(CONF_HOST)
    remote = RemoteControl(host, port)

    add_entities([PanasonicVieraTVDevice(mac, name, remote)])
    return True


class PanasonicVieraTVDevice(MediaPlayerDevice):
    """Representation of a Panasonic Viera TV."""

    def __init__(self, mac, name, remote, uuid=None):
        """Initialize the Panasonic device."""
        import wakeonlan
        # Save a reference to the imported class
        self._wol = wakeonlan
        self._mac = mac
        self._name = name
        self._uuid = uuid
        self._muted = False
        self._playing = True
        self._state = STATE_UNKNOWN
        self._remote = remote
        self._volume = 0

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this Viera TV."""
        return self._uuid

    def update(self):
        """Retrieve the latest data."""
        try:
            self._muted = self._remote.get_mute()
            self._volume = self._remote.get_volume() / 100
            self._state = STATE_ON
        except OSError:
            self._state = STATE_OFF

    def send_key(self, key):
        """Send a key to the tv and handles exceptions."""
        try:
            self._remote.send_key(key)
            self._state = STATE_ON
        except OSError:
            self._state = STATE_OFF
            return False
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._mac:
            return SUPPORT_VIERATV | SUPPORT_TURN_ON
        return SUPPORT_VIERATV

    def turn_on(self):
        """Turn on the media player."""
        if self._mac:
            self._wol.send_magic_packet(self._mac)
            self._state = STATE_ON

    def turn_off(self):
        """Turn off media player."""
        if self._state != STATE_OFF:
            self._remote.turn_off()
            self._state = STATE_OFF

    def volume_up(self):
        """Volume up the media player."""
        self._remote.volume_up()

    def volume_down(self):
        """Volume down media player."""
        self._remote.volume_down()

    def mute_volume(self, mute):
        """Send mute command."""
        self._remote.set_mute(mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volume = int(volume * 100)
        try:
            self._remote.set_volume(volume)
            self._state = STATE_ON
        except OSError:
            self._state = STATE_OFF

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._remote.media_play()

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._remote.media_pause()

    def media_next_track(self):
        """Send next track command."""
        self._remote.media_next_track()

    def media_previous_track(self):
        """Send the previous track command."""
        self._remote.media_previous_track()

    def play_media(self, media_type, media_id, **kwargs):
        """Play media."""
        _LOGGER.debug("Play media: %s (%s)", media_id, media_type)

        if media_type == MEDIA_TYPE_URL:
            try:
                self._remote.open_webpage(media_id)
            except (TimeoutError, OSError):
                self._state = STATE_OFF
        else:
            _LOGGER.warning("Unsupported media_type: %s", media_type)

    def media_stop(self):
        """Stop playback."""
        self.send_key('NRC_CANCEL-ONOFF')
