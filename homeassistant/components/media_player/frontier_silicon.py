"""
Support for Frontier Silicon Devices (Medion, Hama, Auna,...).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.frontier_silicon/
"""
import logging

import asyncio
import requests
import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK,
    SUPPORT_PLAY_MEDIA, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP, SUPPORT_STOP, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_PLAY, SUPPORT_SELECT_SOURCE, MediaPlayerDevice, PLATFORM_SCHEMA)
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

DEFAULT_HOST = '192.168.1.11'
DEFAULT_PORT = 80
DEFAULT_PASSWORD = '1234'
DEVICE_URL = 'http://{0}:{1}/device'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
})


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the Frontier Silicon platform."""
    if discovery_info is not None:
        yield from async_add_entities(
            [FrontierSiliconDevice(discovery_info, DEFAULT_PASSWORD)],
            update_before_add=True)
        return True

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    password = config.get(CONF_PASSWORD)

    try:
        if host and port and password:
            yield from async_add_entities(
                [FrontierSiliconDevice(DEVICE_URL.format(host, port), password)],
                update_before_add=True)
            _LOGGER.info('FSAPI device %s:%s -> %s', host, port, password)
            return True
        else:
            _LOGGER.warning('FSAPI device missing config param %s:%s -> %s',
                            host, port, password)
    except requests.exceptions.RequestException:
        _LOGGER.error('Could not connect to FSAPI device at %s:%s -> %s',
                      host, port, password)


class FrontierSiliconDevice(MediaPlayerDevice):
    """Representation of a Frontier Silicon device on the network."""

    def __init__(self, device_url, password):
        """Initialize the Frontier Silicon API device."""
        self._device_url = device_url
        self._password = password
        self._state = STATE_UNKNOWN

        self._name = None
        self._title = None
        self._mute = None
        self._source = None
        self._source_list = None
        self._media_image_url = None

    @asyncio.coroutine
    def get_fs(self):
        """ Create a fsapi session."""
        from fsapi import FSAPI
        
        return FSAPI(self._device_url, self._password)

    # Properties
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
    def supported_media_commands(self):
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

    # Async actions

    @asyncio.coroutine
    def async_update(self):
        """Get the latest date and update device state."""
        fs_device = yield from self.get_fs()

        if not self._name:
            self._name = fs_device.friendly_name

        if not self._source_list:
            self._source_list = fs_device.mode_list

        title = ''
        artist = fs_device.play_info_artist
        album = fs_device.play_info_album
        info_name = fs_device.play_info_name
        info_text = fs_device.play_info_text

        if artist:
            title += artist
        if album:
            title += ' ('+album+')'
        if info_name:
            if title:
                title += ' - '
            title += info_name
        if info_text:
            title += ': ' + info_text

        self._title = title

        status = fs_device.play_status
        self._state = {
            'playing': STATE_PLAYING,
            'paused': STATE_PAUSED,
            'stopped': STATE_OFF,
            'unknown': STATE_UNKNOWN,
            None: STATE_OFF,
        }.get(status, STATE_UNKNOWN)

        self._source = fs_device.mode
        self._mute = fs_device.mute
        self._media_image_url = fs_device.play_info_graphics

    # Management actions

    # power control
    @asyncio.coroutine
    def async_turn_on(self):
        """Turn on the device."""
        fs_device = yield from self.get_fs()
        fs_device.power = True

    @asyncio.coroutine
    def async_turn_off(self):
        """Turn off the device."""
        fs_device = yield from self.get_fs()
        fs_device.power = False

    @asyncio.coroutine
    def async_media_play(self):
        """Send play command."""
        fs_device = yield from self.get_fs()
        fs_device.play()

    @asyncio.coroutine
    def async_media_pause(self):
        """Send pause command."""
        fs_device = yield from self.get_fs()
        fs_device.pause()

    @asyncio.coroutine
    def async_media_play_pause(self):
        """Send play/pause command."""
        fs_device = yield from self.get_fs()
        if 'playing' in self._state:
            fs_device.pause()
        else:
            fs_device.play()

    @asyncio.coroutine
    def async_media_stop(self):
        """Send play/pause command."""
        fs_device = yield from self.get_fs()
        fs_device.pause()

    @asyncio.coroutine
    def async_media_previous_track(self):
        """Send previous track command (results in rewind)."""
        fs_device = yield from self.get_fs()
        fs_device.prev()

    @asyncio.coroutine
    def async_media_next_track(self):
        """Send next track command (results in fast-forward)."""
        fs_device = yield from self.get_fs()
        fs_device.next()

    # mute
    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @asyncio.coroutine
    def async_mute_volume(self, mute):
        """Send mute command."""
        fs_device = yield from self.get_fs()
        fs_device.mute = mute

    # volume
    @asyncio.coroutine
    def async_volume_up(self):
        """Send volume up command."""
        fs_device = yield from self.get_fs()
        current_volume = fs_device.volume
        fs_device.volume = (current_volume + 1)

    @asyncio.coroutine
    def async_volume_down(self):
        """Send volume down command."""
        fs_device = yield from self.get_fs()
        current_volume = fs_device.volume
        fs_device.volume = (current_volume - 1)

    @asyncio.coroutine
    def async_set_volume_level(self, volume):
        """Set volume command."""
        fs_device = yield from self.get_fs()
        fs_device.volume = volume

    @asyncio.coroutine
    def async_select_source(self, source):
        """Select input source."""
        fs_device = yield from self.get_fs()
        fs_device.mode = source
