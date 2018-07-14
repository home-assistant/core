
"""
Support for broadlink remote control of a media device

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.broadlink/
"""

import asyncio
import voluptuous as vol
import logging
from base64 import b64decode, b64encode
import binascii

from homeassistant.components.media_player import (
    MediaPlayerDevice,
    PLATFORM_SCHEMA,
    ENTITY_ID_FORMAT,
    MEDIA_TYPE_CHANNEL,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_STEP,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PLAY_MEDIA)

from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_MAC,
    CONF_TIMEOUT,
    CONF_TYPE,
    CONF_COMMAND_ON,
    CONF_COMMAND_OFF,
    STATE_OFF,
    STATE_ON,
    STATE_PLAYING,
    STATE_UNKNOWN)

import homeassistant.helpers.config_validation as cv

REQUIREMENTS         = ['broadlink==0.9.0']
DOMAIN               = 'broadlink'

DEFAULT_NAME         = "Broadlink IR Media Player"
DEFAULT_TIMEOUT      = 10
DEFAULT_DELAY        = 0.5

CONF_VOLUME_UP       = 'volume_up'
CONF_VOLUME_DOWN     = 'volume_down'
CONF_VOLUME_MUTE     = 'volume_mute'
CONF_NEXT_TRACK      = 'next_track'
CONF_PREVIOUS_TRACK  = 'previous_track'
CONF_SOURCES         = 'sources'
CONF_CHANNELS        = 'channels'
CONF_DIGITS          = 'digits'
CONF_DIGITDELAY      = 'digitdelay'

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
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
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
    import broadlink

    host = config.get(CONF_HOST)
    mac  = get_broadlink_mac(config.get(CONF_MAC))

    link = broadlink.rm(
        (host, 80),
        mac,
        None)

    await hass.async_add_job(link.auth)

    async_add_devices([BroadlinkRM(hass, link, config)])


def get_supported_by_config(config):
    """ Calculate support flags based on available configuration entries """
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
    """ Convert a mac address string with : in it to just a flat string """
    binascii.unhexlify(mac.encode().replace(b':', b''))


class BroadlinkRM(MediaPlayerDevice):

    def __init__(self, hass, link, config):
        super().__init__()

        self.support = get_supported_by_config(config)
        self.config  = config
        self.hass    = hass

        self.host    = config.get(CONF_HOST)

        self.link    = link
        self._state  = STATE_OFF
        self._source = None

    async def send(self, command):
        if command is None:
            raise Exception('No command defined!')

        packet = b64decode(command)
        await self.hass.async_add_job(self.link.send_data, packet)

    @property
    def name(self):
        return self.config.get(CONF_NAME)

    @property
    def state(self):
        return self._state

    @property
    def supported_features(self):
        return self.support

    async def async_turn_on(self):
        await self.send(self.config.get(CONF_COMMAND_ON))
        self._state = STATE_ON

    async def async_turn_off(self):
        await self.send(self.config.get(CONF_COMMAND_OFF))
        self._state = STATE_OFF

    async def async_volume_up(self):
        await self.send(self.config.get(CONF_VOLUME_UP))

    async def async_volume_down(self):
        await self.send(self.config.get(CONF_VOLUME_DOWN))

    async def async_volume_mute(self):
        await self.send(self.config.get(CONF_VOLUME_MUTE))

    async def async_media_next_track(self):
        await self.send(self.config.get(CONF_NEXT_TRACK))

    async def async_media_previous_track(self):
        await self.send(self.config.get(CONF_PREVIOUS_TRACK))

    async def async_select_source(self, source):
        await self.send(self.config.get(CONF_SOURCES)[source])
        self._source = source

    async def async_play_media(self, media_type, media_id, **kwargs):
        if media_type != MEDIA_TYPE_CHANNEL:
            _LOGGER.error('Unsupported media type %s', media_type)
            return

        cv.positive_int(media_id)

        for digit in media_id:
            await self.send(self.config.get(CONF_DIGITS).get(digit))
            await asyncio.sleep(self.config.get(CONF_DIGITDELAY))

    @property
    def media_content_type(self):
        return MEDIA_TYPE_CHANNEL

    @property
    def source(self):
        return self._source

    @property
    def source_list(self):
        return list(self.config.get(CONF_SOURCES).keys())
