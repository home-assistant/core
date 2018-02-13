"""
Support for interface with a Panasonic Viera TV.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.panasonic_viera/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_PLAY,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, MEDIA_TYPE_URL,
    SUPPORT_PLAY_MEDIA, SUPPORT_STOP,
    SUPPORT_VOLUME_STEP, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN, CONF_PORT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['panasonic_viera==0.3',
                'wakeonlan==1.0.0']

_LOGGER = logging.getLogger(__name__)

CONF_MAC = 'mac'

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


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
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
        remote = RemoteControl(host, port)
        add_devices([PanasonicVieraTVDevice(mac, name, remote)])
        return True

    host = config.get(CONF_HOST)
    remote = RemoteControl(host, port)

    add_devices([PanasonicVieraTVDevice(mac, name, remote)])
    return True


class PanasonicVieraTVDevice(MediaPlayerDevice):
    """Representation of a Panasonic Viera TV."""

    def __init__(self, mac, name, remote):
        """Initialize the Panasonic device."""
        import wakeonlan
        # Save a reference to the imported class
        self._wol = wakeonlan
        self._mac = mac
        self._name = name
        self._muted = False
        self._playing = True
        self._state = STATE_UNKNOWN
        self._remote = remote
        self._volume = 0

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
            self.send_key('NRC_POWER-ONOFF')
            self._state = STATE_OFF

    def volume_up(self):
        """Volume up the media player."""
        self.send_key('NRC_VOLUP-ONOFF')

    def volume_down(self):
        """Volume down media player."""
        self.send_key('NRC_VOLDOWN-ONOFF')

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_key('NRC_MUTE-ONOFF')

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
        self.send_key('NRC_PLAY-ONOFF')

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self.send_key('NRC_PAUSE-ONOFF')

    def media_next_track(self):
        """Send next track command."""
        self.send_key('NRC_FF-ONOFF')

    def media_previous_track(self):
        """Send the previous track command."""
        self.send_key('NRC_REW-ONOFF')

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
