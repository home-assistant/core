"""Support for Openhome Devices."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

import aiohttp
from async_upnp_client.client import UpnpError
from openhomedevice.device import Device
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_PIN_INDEX, DATA_OPENHOME, SERVICE_INVOKE_PIN

_OpenhomeDeviceT = TypeVar("_OpenhomeDeviceT", bound="OpenhomeDevice")
_R = TypeVar("_R")
_P = ParamSpec("_P")

SUPPORT_OPENHOME = (
    MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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
        return

    entity = OpenhomeDevice(hass, device)

    async_add_entities([entity])
    openhome_data.add(device.uuid())

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_INVOKE_PIN,
        {vol.Required(ATTR_PIN_INDEX): cv.positive_int},
        "async_invoke_pin",
    )


_FuncType = Callable[Concatenate[_OpenhomeDeviceT, _P], Awaitable[_R]]
_ReturnFuncType = Callable[
    Concatenate[_OpenhomeDeviceT, _P], Coroutine[Any, Any, _R | None]
]


def catch_request_errors() -> (
    Callable[
        [_FuncType[_OpenhomeDeviceT, _P, _R]], _ReturnFuncType[_OpenhomeDeviceT, _P, _R]
    ]
):
    """Catch asyncio.TimeoutError, aiohttp.ClientError, UpnpError errors."""

    def call_wrapper(
        func: _FuncType[_OpenhomeDeviceT, _P, _R]
    ) -> _ReturnFuncType[_OpenhomeDeviceT, _P, _R]:
        """Call wrapper for decorator."""

        @functools.wraps(func)
        async def wrapper(
            self: _OpenhomeDeviceT, *args: _P.args, **kwargs: _P.kwargs
        ) -> _R | None:
            """Catch asyncio.TimeoutError, aiohttp.ClientError, UpnpError errors."""
            try:
                return await func(self, *args, **kwargs)
            except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError):
                _LOGGER.error("Error during call %s", func.__name__)
            return None

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
        self._attr_supported_features = SUPPORT_OPENHOME
        self._source_names = []
        self._source_index = {}
        self._source = {}
        self._name = None
        self._attr_state = MediaPlayerState.PLAYING
        self._available = True

    @property
    def available(self):
        """Device is available."""
        return self._available

    async def async_update(self) -> None:
        """Update state of device."""
        try:
            self._in_standby = await self._device.is_in_standby()
            self._transport_state = await self._device.transport_state()
            self._track_information = await self._device.track_info()
            self._source = await self._device.source()
            self._name = await self._device.room()
            self._attr_supported_features = SUPPORT_OPENHOME
            source_index = {}
            source_names = []

            if self._device.volume_enabled:
                self._attr_supported_features |= (
                    MediaPlayerEntityFeature.VOLUME_STEP
                    | MediaPlayerEntityFeature.VOLUME_MUTE
                    | MediaPlayerEntityFeature.VOLUME_SET
                )
                self._volume_level = await self._device.volume() / 100.0
                self._volume_muted = await self._device.is_muted()

            for source in await self._device.sources():
                source_names.append(source["name"])
                source_index[source["name"]] = source["index"]

            self._source_index = source_index
            self._source_names = source_names

            if self._source["type"] == "Radio":
                self._attr_supported_features |= (
                    MediaPlayerEntityFeature.STOP
                    | MediaPlayerEntityFeature.PLAY
                    | MediaPlayerEntityFeature.PLAY_MEDIA
                    | MediaPlayerEntityFeature.BROWSE_MEDIA
                )
            if self._source["type"] in ("Playlist", "Spotify"):
                self._attr_supported_features |= (
                    MediaPlayerEntityFeature.PREVIOUS_TRACK
                    | MediaPlayerEntityFeature.NEXT_TRACK
                    | MediaPlayerEntityFeature.PAUSE
                    | MediaPlayerEntityFeature.PLAY
                    | MediaPlayerEntityFeature.PLAY_MEDIA
                    | MediaPlayerEntityFeature.BROWSE_MEDIA
                )

            if self._in_standby:
                self._attr_state = MediaPlayerState.OFF
            elif self._transport_state == "Paused":
                self._attr_state = MediaPlayerState.PAUSED
            elif self._transport_state in ("Playing", "Buffering"):
                self._attr_state = MediaPlayerState.PLAYING
            elif self._transport_state == "Stopped":
                self._attr_state = MediaPlayerState.IDLE
            else:
                # Device is playing an external source with no transport controls
                self._attr_state = MediaPlayerState.PLAYING

            self._available = True
        except (asyncio.TimeoutError, aiohttp.ClientError, UpnpError):
            self._available = False

    @catch_request_errors()
    async def async_turn_on(self) -> None:
        """Bring device out of standby."""
        await self._device.set_standby(False)

    @catch_request_errors()
    async def async_turn_off(self) -> None:
        """Put device in standby."""
        await self._device.set_standby(True)

    @catch_request_errors()
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play_media command to the media player."""
        if media_source.is_media_source_id(media_id):
            media_type = MediaType.MUSIC
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        if media_type != MediaType.MUSIC:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type,
                MediaType.MUSIC,
            )
            return

        media_id = async_process_play_media_url(self.hass, media_id)

        track_details = {"title": "Home Assistant", "uri": media_id}
        await self._device.play_media(track_details)

    @catch_request_errors()
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._device.pause()

    @catch_request_errors()
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._device.stop()

    @catch_request_errors()
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._device.play()

    @catch_request_errors()
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._device.skip(1)

    @catch_request_errors()
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._device.skip(-1)

    @catch_request_errors()
    async def async_select_source(self, source: str) -> None:
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
        except UpnpError:
            _LOGGER.error("Error invoking pin %s", pin)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device.uuid()

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
        if artists := self._track_information.get("artist"):
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
    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self._device.increase_volume()

    @catch_request_errors()
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._device.decrease_volume()

    @catch_request_errors()
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._device.set_volume(int(volume * 100))

    @catch_request_errors()
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._device.set_mute(mute)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )
