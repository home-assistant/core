
"""
Support for broadlink remote control of a media device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.broadlink/
"""

import asyncio
from base64 import b64decode
import binascii
import logging
import socket

import voluptuous as vol

from homeassistant.components.media_player import (
    MEDIA_TYPE_CHANNEL, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK,
    SUPPORT_PLAY_MEDIA, SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP, MediaPlayerDevice)
from homeassistant.const import (
    CONF_COMMAND_OFF, CONF_COMMAND_ON, CONF_HOST, CONF_MAC, CONF_NAME,
    CONF_PORT, CONF_TIMEOUT, STATE_OFF, STATE_ON)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['broadlink==0.9.0']
DOMAIN = 'broadlink'

DEFAULT_NAME = "Broadlink IR Media Player"
DEFAULT_TIMEOUT = 10
DEFAULT_DELAY = 0.5
DEFAULT_PORT = 80

CONF_VOLUME_UP = 'volume_up'
CONF_VOLUME_DOWN = 'volume_down'
CONF_VOLUME_MUTE = 'volume_mute'
CONF_NEXT_TRACK = 'next_track'
CONF_PREVIOUS_TRACK = 'previous_track'
CONF_SOURCES = 'sources'
CONF_CHANNELS = 'channels'
CONF_DIGITS = 'digits'
CONF_DIGITDELAY = 'digitdelay'

DIGITS_SCHEMA = vol.Schema({
    vol.Required('0'): cv.string,
    vol.Required('1'): cv.string,
    vol.Required('2'): cv.string,
    vol.Required('3'): cv.string,
    vol.Required('4'): cv.string,
    vol.Required('5'): cv.string,
    vol.Required('6'): cv.string,
    vol.Required('7'): cv.string,
    vol.Required('8'): cv.string,
    vol.Required('9'): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.ipv4_address,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
    vol.Required(CONF_MAC): cv.mac_address,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,

    vol.Optional(CONF_DIGITDELAY, default=DEFAULT_DELAY): float,
    vol.Optional(CONF_COMMAND_ON): cv.string,
    vol.Optional(CONF_COMMAND_OFF): cv.string,
    vol.Optional(CONF_VOLUME_UP): cv.string,
    vol.Optional(CONF_VOLUME_DOWN): cv.string,
    vol.Optional(CONF_VOLUME_MUTE): cv.string,
    vol.Optional(CONF_NEXT_TRACK): cv.string,
    vol.Optional(CONF_PREVIOUS_TRACK): cv.string,
    vol.Optional(CONF_SOURCES, default={}): dict,
    vol.Optional(CONF_DIGITS): DIGITS_SCHEMA,
})

SUPPORT_MAPPING = [
    (CONF_COMMAND_ON, SUPPORT_TURN_ON),
    (CONF_COMMAND_OFF, SUPPORT_TURN_OFF),
    (CONF_VOLUME_UP, SUPPORT_VOLUME_STEP),
    (CONF_VOLUME_DOWN, SUPPORT_VOLUME_STEP),
    (CONF_VOLUME_MUTE, SUPPORT_VOLUME_MUTE),
    (CONF_NEXT_TRACK, SUPPORT_NEXT_TRACK),
    (CONF_PREVIOUS_TRACK, SUPPORT_PREVIOUS_TRACK),
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass,
                               config,
                               async_add_devices,
                               discovery_info=None):
    """Set up platform."""
    import broadlink

    host = (config.get(CONF_HOST),
            config.get(CONF_PORT))
    mac = get_broadlink_mac(config.get(CONF_MAC))

    link = broadlink.rm(
        host,
        mac,
        None)

    try:
        await hass.async_add_job(link.auth)
    except socket.timeout:
        _LOGGER.warning("Timeout trying to authenticate to broadlink")
        raise PlatformNotReady

    async_add_devices([BroadlinkRM(link, config)])


def get_supported_by_config(config):
    """Calculate support flags based on available configuration entries."""
    support = 0

    for mapping in SUPPORT_MAPPING:
        if mapping[0] in config:
            support = support | mapping[1]

    if config.get(CONF_SOURCES):
        support = support | SUPPORT_SELECT_SOURCE

    if config.get(CONF_DIGITS):
        support = support | SUPPORT_PLAY_MEDIA

    return support


def get_broadlink_mac(mac: str):
    """Convert a mac address string with : in it to just a flat string."""
    return binascii.unhexlify(mac.encode().replace(b':', b''))


class BroadlinkRM(MediaPlayerDevice):
    """Representation of a media device."""

    def __init__(self, link, config):
        """Initialize device."""
        super().__init__()

        self._support = get_supported_by_config(config)
        self._config = config
        self._link = link
        self._state = STATE_OFF
        self._source = None

    async def send(self, command):
        """Send b64 encoded command to device."""
        if command is None:
            raise Exception('No command defined!')

        packet = b64decode(command)
        await self.hass.async_add_job(self._link.send_data, packet)

    @property
    def name(self):
        """Return the name of the controlled device."""
        return self._config.get(CONF_NAME)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return self._support

    async def async_turn_on(self):
        """Turn on media player."""
        await self.send(self._config.get(CONF_COMMAND_ON))
        self._state = STATE_ON

    async def async_turn_off(self):
        """Turn off media player."""
        await self.send(self._config.get(CONF_COMMAND_OFF))
        self._state = STATE_OFF

    async def async_volume_up(self):
        """Volume up media player."""
        await self.send(self._config.get(CONF_VOLUME_UP))

    async def async_volume_down(self):
        """Volume down media player."""
        await self.send(self._config.get(CONF_VOLUME_DOWN))

    async def async_volume_mute(self):
        """Send mute command."""
        await self.send(self._config.get(CONF_VOLUME_MUTE))

    async def async_media_next_track(self):
        """Send next track command."""
        await self.send(self._config.get(CONF_NEXT_TRACK))

    async def async_media_previous_track(self):
        """Send the previous track command."""
        await self.send(self._config.get(CONF_PREVIOUS_TRACK))

    async def async_select_source(self, source):
        await self.send(self._config.get(CONF_SOURCES)[source])
        self._source = source

    async def async_play_media(self, media_type, media_id, **kwargs):
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error('Unsupported media type %s', media_type)
            return

        cv.positive_int(media_id)

        for digit in media_id:
            await self.send(self._config.get(CONF_DIGITS).get(digit))
            await asyncio.sleep(self._config.get(CONF_DIGITDELAY))

    @property
    def media_content_type(self):
        """Return content type currently active."""
        return MEDIA_TYPE_CHANNEL

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._config.get(CONF_SOURCES).keys())
