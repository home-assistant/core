"""Support for Openhome Devices."""

from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import Any, Concatenate, override

from openhomedevice.exceptions import OpenhomeError

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.const import (
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenhomeConfigEntry
from .const import DOMAIN
from .services import SERVICE_INVOKE_PIN

SUPPORT_OPENHOME = (
    MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenhomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Openhome config entry."""

    _LOGGER.debug("Setting up config entry: %s", config_entry.unique_id)

    device = config_entry.runtime_data

    entity = OpenhomeDevice(device)

    async_add_entities([entity])


type _FuncType[_T, **_P, _R] = Callable[Concatenate[_T, _P], Awaitable[_R]]
type _ReturnFuncType[_T, **_P, _R] = Callable[
    Concatenate[_T, _P], Coroutine[Any, Any, _R]
]


def catch_request_errors[_OpenhomeDeviceT: OpenhomeDevice, **_P, _R](
    action: str,
) -> Callable[
    [_FuncType[_OpenhomeDeviceT, _P, _R]], _ReturnFuncType[_OpenhomeDeviceT, _P, _R]
]:
    """Return decorator that catches errors and raises HomeAssistantError."""

    def call_wrapper(
        func: _FuncType[_OpenhomeDeviceT, _P, _R],
    ) -> _ReturnFuncType[_OpenhomeDeviceT, _P, _R]:
        """Call wrapper for decorator."""

        @functools.wraps(func)
        async def wrapper(
            self: _OpenhomeDeviceT, *args: _P.args, **kwargs: _P.kwargs
        ) -> _R:
            """Catch OpenhomeError errors."""
            try:
                return await func(self, *args, **kwargs)
            except OpenhomeError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=action,
                ) from err

        return wrapper

    return call_wrapper


class OpenhomeDevice(MediaPlayerEntity):
    """Representation of an Openhome device."""

    _attr_supported_features = SUPPORT_OPENHOME
    _attr_state = MediaPlayerState.PLAYING
    _attr_available = True

    def __init__(self, device):
        """Initialise the Openhome device."""
        self._device = device
        self._attr_unique_id = device.uuid()
        self._source_index = {}
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device.uuid()),
            },
            manufacturer=device.manufacturer(),
            model=device.model_name(),
            name=device.friendly_name(),
        )

    async def async_update(self) -> None:
        """Update state of device."""
        try:
            self._attr_name = await self._device.room()
            self._attr_supported_features = SUPPORT_OPENHOME
            source_index = {}
            source_names = []

            track_information = await self._device.track_info()
            self._attr_media_image_url = track_information.get("albumArtwork")
            self._attr_media_album_name = track_information.get("albumTitle")
            self._attr_media_title = track_information.get("title")
            if artists := track_information.get("artist"):
                self._attr_media_artist = artists[0]
            self._attr_media_content_id = track_information.get("uri")
            self._attr_media_content_type = MediaType.MUSIC

            if self._device.volume_enabled:
                self._attr_supported_features |= (
                    MediaPlayerEntityFeature.VOLUME_STEP
                    | MediaPlayerEntityFeature.VOLUME_MUTE
                    | MediaPlayerEntityFeature.VOLUME_SET
                )
                self._attr_volume_level = await self._device.volume() / 100.0
                self._attr_is_volume_muted = await self._device.is_muted()

            for source in await self._device.sources():
                source_names.append(source["name"])
                source_index[source["name"]] = source["index"]

            source = await self._device.source()
            self._attr_source = source.get("name")
            self._source_index = source_index
            self._attr_source_list = source_names

            if source["type"] in ("Radio", "Receiver"):
                self._attr_supported_features |= (
                    MediaPlayerEntityFeature.STOP
                    | MediaPlayerEntityFeature.PLAY
                    | MediaPlayerEntityFeature.PLAY_MEDIA
                    | MediaPlayerEntityFeature.BROWSE_MEDIA
                )
            if source["type"] in ("Playlist", "Spotify"):
                self._attr_supported_features |= (
                    MediaPlayerEntityFeature.PREVIOUS_TRACK
                    | MediaPlayerEntityFeature.NEXT_TRACK
                    | MediaPlayerEntityFeature.PAUSE
                    | MediaPlayerEntityFeature.PLAY
                    | MediaPlayerEntityFeature.PLAY_MEDIA
                    | MediaPlayerEntityFeature.BROWSE_MEDIA
                )

            in_standby = await self._device.is_in_standby()
            transport_state = await self._device.transport_state()
            if in_standby:
                self._attr_state = MediaPlayerState.OFF
            elif transport_state == "Paused":
                self._attr_state = MediaPlayerState.PAUSED
            elif transport_state in ("Playing", "Buffering"):
                self._attr_state = MediaPlayerState.PLAYING
            elif transport_state == "Stopped":
                self._attr_state = MediaPlayerState.IDLE
            else:
                # Device is playing an external source with no transport controls
                self._attr_state = MediaPlayerState.PLAYING

            self._attr_available = True
        except OpenhomeError as err:
            if self._attr_available:
                _LOGGER.warning("Error updating %s: %s", self.entity_id, err)
            self._attr_available = False

    @catch_request_errors(SERVICE_TURN_ON)
    @override
    async def async_turn_on(self) -> None:
        """Bring device out of standby."""
        await self._device.set_standby(False)

    @catch_request_errors(SERVICE_TURN_OFF)
    @override
    async def async_turn_off(self) -> None:
        """Put device in standby."""
        await self._device.set_standby(True)

    @catch_request_errors(SERVICE_PLAY_MEDIA)
    @override
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

    @catch_request_errors(SERVICE_MEDIA_PAUSE)
    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._device.pause()

    @catch_request_errors(SERVICE_MEDIA_STOP)
    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._device.stop()

    @catch_request_errors(SERVICE_MEDIA_PLAY)
    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._device.play()

    @catch_request_errors(SERVICE_MEDIA_NEXT_TRACK)
    @override
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._device.skip(1)

    @catch_request_errors(SERVICE_MEDIA_PREVIOUS_TRACK)
    @override
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._device.skip(-1)

    @catch_request_errors(SERVICE_SELECT_SOURCE)
    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._device.set_source(self._source_index[source])

    @catch_request_errors(SERVICE_INVOKE_PIN)
    async def async_invoke_pin(self, pin):
        """Invoke pin."""
        if not self._device.pins_enabled:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="pins_not_supported",
            )
        await self._device.invoke_pin(pin)

    @catch_request_errors(SERVICE_VOLUME_UP)
    @override
    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self._device.increase_volume()

    @catch_request_errors(SERVICE_VOLUME_DOWN)
    @override
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._device.decrease_volume()

    @catch_request_errors(SERVICE_VOLUME_SET)
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._device.set_volume(int(volume * 100))

    @catch_request_errors(SERVICE_VOLUME_MUTE)
    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._device.set_mute(mute)

    @override
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
