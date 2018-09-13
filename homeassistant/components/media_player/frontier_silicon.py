"""
Support for Frontier Silicon Devices (Medion, Hama, Auna,...).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.frontier_silicon/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PLAY, SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP,
    MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['afsapi==0.0.4']

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


@asyncio.coroutine
def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Frontier Silicon platform."""
    import requests

    if discovery_info is not None:
        async_add_entities(
            [AFSAPIDevice(
                discovery_info['ssdp_description'], DEFAULT_PASSWORD)], True)
        return True

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    password = config.get(CONF_PASSWORD)

    try:
        async_add_entities(
            [AFSAPIDevice(DEVICE_URL.format(host, port), password)], True)
        _LOGGER.debug("FSAPI device %s:%s -> %s", host, port, password)
        return True
    except requests.exceptions.RequestException:
        _LOGGER.error("Could not add the FSAPI device at %s:%s -> %s",
                      host, port, password)

    return False


class AFSAPIDevice(MediaPlayerDevice):
    """Representation of a Frontier Silicon device on the network."""

    def __init__(self, device_url, password):
        """Initialize the Frontier Silicon API device."""
        self._device_url = device_url
        self._password = password
        self._state = None

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
        from afsapi import AFSAPI

        return AFSAPI(self._device_url, self._password)

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

    @asyncio.coroutine
    def async_update(self):
        """Get the latest date and update device state."""
        fs_device = self.fs_device

        if not self._name:
            self._name = yield from fs_device.get_friendly_name()

        if not self._source_list:
            self._source_list = yield from fs_device.get_mode_list()

        status = yield from fs_device.get_play_status()
        self._state = {
            'playing': STATE_PLAYING,
            'paused': STATE_PAUSED,
            'stopped': STATE_OFF,
            'unknown': STATE_UNKNOWN,
            None: STATE_OFF,
        }.get(status, STATE_UNKNOWN)

        if self._state != STATE_OFF:
            info_name = yield from fs_device.get_play_name()
            info_text = yield from fs_device.get_play_text()

            self._title = ' - '.join(filter(None, [info_name, info_text]))
            self._artist = yield from fs_device.get_play_artist()
            self._album_name = yield from fs_device.get_play_album()

            self._source = yield from fs_device.get_mode()
            self._mute = yield from fs_device.get_mute()
            self._media_image_url = yield from fs_device.get_play_graphic()
        else:
            self._title = None
            self._artist = None
            self._album_name = None

            self._source = None
            self._mute = None
            self._media_image_url = None

    # Management actions
    # power control
    @asyncio.coroutine
    def async_turn_on(self):
        """Turn on the device."""
        yield from self.fs_device.set_power(True)

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn off the device."""
        yield from self.fs_device.set_power(False)

    @asyncio.coroutine
    def async_media_play(self):
        """Send play command."""
        yield from self.fs_device.play()

    @asyncio.coroutine
    def async_media_pause(self):
        """Send pause command."""
        yield from self.fs_device.pause()

    @asyncio.coroutine
    def async_media_play_pause(self):
        """Send play/pause command."""
        if 'playing' in self._state:
            yield from self.fs_device.pause()
        else:
            yield from self.fs_device.play()

    @asyncio.coroutine
    def async_media_stop(self):
        """Send play/pause command."""
        yield from self.fs_device.pause()

    @asyncio.coroutine
    def async_media_previous_track(self):
        """Send previous track command (results in rewind)."""
        yield from self.fs_device.rewind()

    @asyncio.coroutine
    def async_media_next_track(self):
        """Send next track command (results in fast-forward)."""
        yield from self.fs_device.forward()

    # mute
    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Send mute command."""
        yield from self.fs_device.set_mute(mute)

    # volume
    @asyncio.coroutine
    def async_volume_up(self):
        """Send volume up command."""
        volume = yield from self.fs_device.get_volume()
        yield from self.fs_device.set_volume(volume+1)

    @asyncio.coroutine
    def async_volume_down(self):
        """Send volume down command."""
        volume = yield from self.fs_device.get_volume()
        yield from self.fs_device.set_volume(volume-1)

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set volume command."""
        yield from self.fs_device.set_volume(volume)

    @asyncio.coroutine
    def async_select_source(self, source):
        """Select input source."""
        yield from self.fs_device.set_mode(source)
