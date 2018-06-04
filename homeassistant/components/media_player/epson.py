"""
Support for Epson projector.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/media_player.epson/
"""
import asyncio
import logging

import aiohttp
from epson_projector.const import (
    BACK, BUSY, CMODE, CMODE_LIST, CMODE_LIST_SET, DEFAULT_SOURCES,
    EPSON_CODES, FAST, INV_SOURCES, MUTE, PAUSE, PLAY, POWER, SOURCE,
    SOURCE_LIST, TURN_OFF, TURN_ON, VOL_DOWN, VOL_UP, VOLUME)
from homeassistant.components.media_player import (
    DOMAIN, MEDIA_PLAYER_SCHEMA, PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    MediaPlayerDevice)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT, CONF_SSL, STATE_OFF,
    STATE_ON)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

REQUIREMENTS = ['epson-projector==0.1.1']

DATA_EPSON = 'epson'
DEFAULT_NAME = 'EPSON Projector'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=80): cv.port,
    vol.Optional(CONF_SSL, default=False): cv.boolean
})

ATTR_CMODE = 'cmode'
SUPPORT_CMODE = 33001

SUPPORT_EPSON = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE |\
            SUPPORT_CMODE | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_STEP | \
            SUPPORT_NEXT_TRACK | SUPPORT_PREVIOUS_TRACK

EPSON_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Optional(ATTR_CMODE): cv.string
})

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info=None):
    """Set up the Epson media player platform."""
    if DATA_EPSON not in hass.data:
        hass.data[DATA_EPSON] = []
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    try:
        epson = EpsonProjector(
            hass, name, host,
            config.get(CONF_PORT), config.get(CONF_SSL))
        await epson.update()
    except (aiohttp.client_exceptions.ClientConnectorError,
            asyncio.TimeoutError):
        raise PlatformNotReady
    if epson:
        hass.data[DATA_EPSON].append(epson)
        async_add_devices([epson], update_before_add=True)

    async def async_service_handler(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [device for device in hass.data[DATA_EPSON]
                       if device.entity_id in entity_ids]
        else:
            devices = hass.data[DATA_EPSON]
        for device in devices:
            if service.service == ATTR_CMODE:
                cmode = service.data.get(ATTR_CMODE).lower()
                if cmode in CMODE_LIST_SET:
                    await device.select_cmode(cmode)
            await device.update()
    hass.services.async_register(
        DOMAIN, ATTR_CMODE, async_service_handler,
        schema=EPSON_SCHEMA)
    return True


class EpsonProjector(MediaPlayerDevice):
    """Representation of Epson Projector Device."""

    def __init__(self, hass, name, host, port, encryption):
        """Initialize entity to control Epson projector."""
        self._hass = hass
        self._name = name
        import epson_projector as epson
        self._projector = epson.Projector(
            host,
            websession=self._websession(False),
            port=port)

        self._cmode = None
        self._source_list = list(DEFAULT_SOURCES.values())
        self._source = None
        self._volume = None

        self._state = None

    def _websession(self, verify_ssl):
        """Return a websession."""
        return async_get_clientsession(self._hass, verify_ssl)

    async def update(self):
        """Update state of device."""
        is_turned_on = await self._projector.get_property(POWER)
        _LOGGER.debug("Is turned on %s", is_turned_on)
        if is_turned_on and is_turned_on == EPSON_CODES[POWER]:
            self._state = STATE_ON
            cmode = await self._projector.get_property(CMODE)
            if cmode and cmode in CMODE_LIST:
                self._cmode = CMODE_LIST[cmode]
            source = await self._projector.get_property(SOURCE)
            if source and source in SOURCE_LIST:
                self._source = SOURCE_LIST[source]
            volume = await self._projector.get_property(VOLUME)
            if volume:
                self._volume = volume
        elif is_turned_on == BUSY:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_EPSON

    async def async_turn_on(self):
        """Turn on epson."""
        return await self._projector.send_command(TURN_ON)

    async def async_turn_off(self):
        """Turn off epson."""
        return await self._projector.send_command(TURN_OFF)

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def source(self):
        """Get current input sources."""
        return self._source

    @property
    def cmode(self):
        """Get CMODE/color mode from Epson."""
        return self._cmode

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return self._volume

    async def select_cmode(self, cmode):
        """Set color mode in Epson."""
        if cmode in CMODE_LIST_SET:
            return await self._projector.send_command(CMODE_LIST_SET[cmode])

    async def async_select_source(self, source):
        """Select input source."""
        _LOGGER.debug("select source")
        selected_source = INV_SOURCES[source]
        return await self._projector.send_command(selected_source)

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) sound."""
        return await self._projector.send_command(MUTE)

    async def async_volume_up(self):
        """Increase volume."""
        _LOGGER.debug("volume up")
        return await self._projector.send_command(VOL_UP)

    async def async_volume_down(self):
        """Decrease volume."""
        return await self._projector.send_command(VOL_DOWN)

    async def async_media_play(self):
        """Play media via Epson."""
        return await self._projector.send_command(PLAY)

    async def async_media_pause(self):
        """Pause media via Epson."""
        return await self._projector.send_command(PAUSE)

    async def async_media_next_track(self):
        """Skip to next."""
        return await self._projector.send_command(FAST)

    async def async_media_previous_track(self):
        """Skip to previous."""
        return await self._projector.send_command(BACK)

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if self._cmode is not None:
            attributes[ATTR_CMODE] = self._cmode
        return attributes
