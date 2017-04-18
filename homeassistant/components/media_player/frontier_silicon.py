"""
Support for Frontier Silicon Devices (Medion, Hama, Auna,...).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.frontier_silicon/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_PLAY_MEDIA, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_PLAY, SUPPORT_SELECT_SOURCE, MediaPlayerDevice, PLATFORM_SCHEMA,
    MEDIA_TYPE_MUSIC)
from homeassistant.const import (
    STATE_OFF, STATE_PLAYING, STATE_PAUSED, STATE_UNKNOWN,
    CONF_HOST, CONF_PORT, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['fsapi==0.0.7']

_LOGGER = logging.getLogger(__name__)

SUPPORT_FRONTIER_SILICON = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | \
    SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_SEEK | \
    SUPPORT_PLAY_MEDIA | SUPPORT_PLAY | SUPPORT_STOP | SUPPORT_TURN_ON | \
    SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

DEFAULT_PORT = 80
DEFAULT_PASSWORD = '1234'
DEVICE_URL = 'http://{0}:{1}/device'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Frontier Silicon platform."""
    import requests

    if discovery_info is not None:
        add_devices(
            [FSAPIDevice(discovery_info['ssdp_description'],
                         DEFAULT_PASSWORD)],
            update_before_add=True)
        return True

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    password = config.get(CONF_PASSWORD)

    try:
        add_devices(
            [FSAPIDevice(DEVICE_URL.format(host, port), password)],
            update_before_add=True)
        _LOGGER.debug("FSAPI device %s:%s -> %s", host, port, password)
        return True
    except requests.exceptions.RequestException:
        _LOGGER.error("Could not add the FSAPI device at %s:%s -> %s",
                      host, port, password)

    return False


class FSAPIDevice(MediaPlayerDevice):
    """Representation of a Frontier Silicon device on the network."""

    def __init__(self, device_url, password):
        """Initialize the Frontier Silicon API device."""
        self._device_url = device_url
        self._password = password
        self._state = STATE_UNKNOWN

        self._name = None
        self._title = None
        self._artist = None
        self._album_name = None
        self._mute = None
        self._source = None
        self._source_list = None
        self._media_image_url = None

    # Properties
    @property
    def fs_device(self):
        """
        Create a fresh fsapi session.

        A new session is created for each request in case someone else
        connected to the device in between the updates and invalidated the
        existing session (i.e UNDOK).
        """
        from fsapi import FSAPI

        return FSAPI(self._device_url, self._password)

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._title

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._artist

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._album_name

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORT_FRONTIER_SILICON

    @property
    def state(self):
        """Return the state of the player."""
        return self._state

    # source
    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._media_image_url

    def update(self):
        """Get the latest date and update device state."""
        fs_device = self.fs_device

        if not self._name:
            self._name = fs_device.friendly_name

        if not self._source_list:
            self._source_list = fs_device.mode_list

        status = fs_device.play_status
        self._state = {
            'playing': STATE_PLAYING,
            'paused': STATE_PAUSED,
            'stopped': STATE_OFF,
            'unknown': STATE_UNKNOWN,
            None: STATE_OFF,
        }.get(status, STATE_UNKNOWN)

        info_name = fs_device.play_info_name
        info_text = fs_device.play_info_text

        self._title = ' - '.join(filter(None, [info_name, info_text]))
        self._artist = fs_device.play_info_artist
        self._album_name = fs_device.play_info_album

        self._source = fs_device.mode
        self._mute = fs_device.mute
        self._media_image_url = fs_device.play_info_graphics

    # Management actions

    # power control
    def turn_on(self):
        """Turn on the device."""
        self.fs_device.power = True

    def turn_off(self):
        """Turn off the device."""
        self.fs_device.power = False

    def media_play(self):
        """Send play command."""
        self.fs_device.play()

    def media_pause(self):
        """Send pause command."""
        self.fs_device.pause()

    def media_play_pause(self):
        """Send play/pause command."""
        if 'playing' in self._state:
            self.fs_device.pause()
        else:
            self.fs_device.play()

    def media_stop(self):
        """Send play/pause command."""
        self.fs_device.pause()

    def media_previous_track(self):
        """Send previous track command (results in rewind)."""
        self.fs_device.prev()

    def media_next_track(self):
        """Send next track command (results in fast-forward)."""
        self.fs_device.next()

    # mute
    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    def mute_volume(self, mute):
        """Send mute command."""
        self.fs_device.mute = mute

    # volume
    def volume_up(self):
        """Send volume up command."""
        self.fs_device.volume += 1

    def volume_down(self):
        """Send volume down command."""
        self.fs_device.volume -= 1

    def set_volume_level(self, volume):
        """Set volume command."""
        self.fs_device.volume = volume

    def select_source(self, source):
        """Select input source."""
        self.fs_device.mode = source
