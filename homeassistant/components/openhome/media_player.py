"""Support for Openhome Devices."""
import asyncio
import functools
import logging

import aiohttp
from async_upnp_client.client import UpnpError
from openhomedevice.device import Device
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import ATTR_PIN_INDEX, DATA_OPENHOME, SERVICE_INVOKE_PIN

SUPPORT_OPENHOME = SUPPORT_SELECT_SOURCE | SUPPORT_TURN_OFF | SUPPORT_TURN_ON

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Openhome platform."""

    if not discovery_info:
        return

    openhome_data = hass.data.setdefault(DATA_OPENHOME, set())

    name = discovery_info.get("name")
    description = discovery_info.get("ssdp_description")

    _LOGGER.info("Openhome device found: %s", name)
    device = await hass.async_add_executor_job(Device, description)
    await device.init()

    # if device has already been discovered
    if device.uuid() in openhome_data:
        return True

    entity = OpenhomeDevice(hass, device)

    async_add_entities([entity])
    openhome_data.add(device.uuid())

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_INVOKE_PIN,
        {vol.Required(ATTR_PIN_INDEX): cv.positive_int},
        "async_invoke_pin",
    )


def catch_request_errors():
    """Catch asyncio.TimeoutError, aiohttp.ClientError, UpnpError errors."""

    def call_wrapper(func):
        """Call wrapper for decorator."""

        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            """Catch asyncio.TimeoutError, aiohttp.ClientError, UpnpError errors."""
            try:
                return await func(self, *args, **kwargs)
            except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError):
                _LOGGER.error("Error during call %s", func.__name__)

        return wrapper

    return call_wrapper


class OpenhomeDevice(MediaPlayerEntity):
    """Representation of an Openhome device."""

    def __init__(self, hass, device):
        """Initialise the Openhome device."""
        self.hass = hass
        self._device = device
        self._track_information = {}
        self._in_standby = None
        self._transport_state = None
        self._volume_level = None
        self._volume_muted = None
        self._supported_features = SUPPORT_OPENHOME
        self._source_names = []
        self._source_index = {}
        self._source = {}
        self._name = None
        self._state = STATE_PLAYING
        self._available = True

    @property
    def available(self):
        """Device is available."""
        return self._available

    async def async_update(self):
        """Update state of device."""
        try:
            self._in_standby = await self._device.is_in_standby()
            self._transport_state = await self._device.transport_state()
            self._track_information = await self._device.track_info()
            self._source = await self._device.source()
            self._name = await self._device.room()
            self._supported_features = SUPPORT_OPENHOME
            source_index = {}
            source_names = []

            if self._device.volume_enabled:
                self._supported_features |= (
                    SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET
                )
                self._volume_level = await self._device.volume() / 100.0
                self._volume_muted = await self._device.is_muted()

            for source in await self._device.sources():
                source_names.append(source["name"])
                source_index[source["name"]] = source["index"]

            self._source_index = source_index
            self._source_names = source_names

            if self._source["type"] == "Radio":
                self._supported_features |= (
                    SUPPORT_STOP | SUPPORT_PLAY | SUPPORT_PLAY_MEDIA
                )
            if self._source["type"] in ("Playlist", "Spotify"):
                self._supported_features |= (
                    SUPPORT_PREVIOUS_TRACK
                    | SUPPORT_NEXT_TRACK
                    | SUPPORT_PAUSE
                    | SUPPORT_PLAY
                    | SUPPORT_PLAY_MEDIA
                )

            if self._in_standby:
                self._state = STATE_OFF
            elif self._transport_state == "Paused":
                self._state = STATE_PAUSED
            elif self._transport_state in ("Playing", "Buffering"):
                self._state = STATE_PLAYING
            elif self._transport_state == "Stopped":
                self._state = STATE_IDLE
            else:
                # Device is playing an external source with no transport controls
                self._state = STATE_PLAYING

            self._available = True
        except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError):
            self._available = False

    @catch_request_errors()
    async def async_turn_on(self):
        """Bring device out of standby."""
        await self._device.set_standby(False)

    @catch_request_errors()
    async def async_turn_off(self):
        """Put device in standby."""
        await self._device.set_standby(True)

    @catch_request_errors()
    async def async_play_media(self, media_type, media_id, **kwargs):
        """Send the play_media command to the media player."""
        if media_type != MEDIA_TYPE_MUSIC:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type,
                MEDIA_TYPE_MUSIC,
            )
            return
        track_details = {"title": "Home Assistant", "uri": media_id}
        await self._device.play_media(track_details)

    @catch_request_errors()
    async def async_media_pause(self):
        """Send pause command."""
        await self._device.pause()

    @catch_request_errors()
    async def async_media_stop(self):
        """Send stop command."""
        await self._device.stop()

    @catch_request_errors()
    async def async_media_play(self):
        """Send play command."""
        await self._device.play()

    @catch_request_errors()
    async def async_media_next_track(self):
        """Send next track command."""
        await self._device.skip(1)

    @catch_request_errors()
    async def async_media_previous_track(self):
        """Send previous track command."""
        await self._device.skip(-1)

    @catch_request_errors()
    async def async_select_source(self, source):
        """Select input source."""
        await self._device.set_source(self._source_index[source])

    @catch_request_errors()
    async def async_invoke_pin(self, pin):
        """Invoke pin."""
        try:
            if self._device.pins_enabled:
                await self._device.invoke_pin(pin)
            else:
                _LOGGER.error("Pins service not supported")
        except (UpnpError):
            _LOGGER.error("Error invoking pin %s", pin)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def supported_features(self):
        """Flag of features commands that are supported."""
        return self._supported_features

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device.uuid()

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._track_information.get("albumArtwork")

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        artists = self._track_information.get("artist")
        if artists:
            return artists[0]

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self._track_information.get("albumTitle")

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._track_information.get("title")

    @property
    def source(self):
        """Name of the current input source."""
        return self._source.get("name")

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume_level

    @property
    def is_volume_muted(self):
        """Return true if volume is muted."""
        return self._volume_muted

    @catch_request_errors()
    async def async_volume_up(self):
        """Volume up media player."""
        await self._device.increase_volume()

    @catch_request_errors()
    async def async_volume_down(self):
        """Volume down media player."""
        await self._device.decrease_volume()

    @catch_request_errors()
    async def async_set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        await self._device.set_volume(int(volume * 100))

    @catch_request_errors()
    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        await self._device.set_mute(mute)
