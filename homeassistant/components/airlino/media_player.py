"""Media player platform for AirLino."""

from collections.abc import Awaitable, Callable
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, override
from urllib.parse import urlsplit

from airlino_api import (
    PLAYER_STATE_PAUSED,
    PLAYER_STATE_PLAYING,
    PLAYER_STATE_STOPPED,
    VOLUME_MAX,
    AirlinoApiConnectionError,
    AirlinoApiError,
)

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.components.media_source import is_media_source_id
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirlinoConfigEntry, AirlinoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

STATE_MAP = {
    PLAYER_STATE_STOPPED: MediaPlayerState.IDLE,
    PLAYER_STATE_PLAYING: MediaPlayerState.PLAYING,
    PLAYER_STATE_PAUSED: MediaPlayerState.PAUSED,
}

SOURCE_TO_MEDIA_TYPE = {
    "radio": MediaType.CHANNEL,
    "tidal": MediaType.MUSIC,
    "qobuz": MediaType.MUSIC,
    "other": MediaType.MUSIC,
}


def _is_valid_media_url(media_id: str) -> bool:
    """Return whether the media ID is an HTTP(S) URL or a Home Assistant path."""
    if media_id.startswith("/"):
        return True
    url = urlsplit(media_id)
    return url.scheme in ("http", "https") and bool(url.hostname)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirlinoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AirLino media player from a config entry."""
    async_add_entities([AirlinoMediaPlayer(entry.runtime_data, entry)])


class AirlinoMediaPlayer(
    CoordinatorEntity[AirlinoDataUpdateCoordinator], MediaPlayerEntity
):
    """Representation of an AirLino media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def __init__(
        self,
        coordinator: AirlinoDataUpdateCoordinator,
        entry: AirlinoConfigEntry,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert entry.unique_id is not None
        self._attr_unique_id = entry.unique_id
        device = coordinator.device_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, entry.unique_id)},
            name=device.get("devicename") or entry.title,
            manufacturer="LinTech GmbH",
            model=device.get("model"),
            sw_version=device.get("firmware"),
        )

    @override
    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current playback state."""
        player = self.coordinator.data.player
        return STATE_MAP.get(player.get("state"))

    @override
    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0.0 - 1.0)."""
        return self.coordinator.data.volume / VOLUME_MAX

    @override
    @property
    def media_content_type(self) -> MediaType | None:
        """Content type of current playing media."""
        status = self.coordinator.data.player.get("status") or {}
        return SOURCE_TO_MEDIA_TYPE.get(status.get("source", ""))

    @override
    @property
    def media_title(self) -> str | None:
        """Return the title of the current media."""
        status = self.coordinator.data.player.get("status") or {}
        station = status.get("station") or {}
        meta = station.get("meta") or {}
        if meta.get("now_playing"):
            return meta["now_playing"]
        if station.get("name"):
            return station["name"]
        track = status.get("track") or {}
        track_meta = track.get("meta") or {}
        if track_meta.get("title"):
            title = track_meta["title"]
            if track_meta.get("artist"):
                title = f"{track_meta['artist']} - {title}"
            return title
        return None

    @override
    @property
    def media_image_url(self) -> str | None:
        """Return the image URL of the current media."""
        status = self.coordinator.data.player.get("status") or {}
        station = status.get("station") or {}
        track = status.get("track") or {}
        return station.get("image") or track.get("image")

    @override
    @property
    def media_duration(self) -> int | None:
        """Return the duration of the current track in seconds."""
        status = self.coordinator.data.player.get("status") or {}
        track = status.get("track") or {}
        return track.get("totaltime")

    @override
    @property
    def media_position(self) -> int | None:
        """Return the elapsed playback time in seconds."""
        status = self.coordinator.data.player.get("status") or {}
        return status.get("elapsedtime")

    @override
    @property
    def media_position_updated_at(self) -> datetime | None:
        """When the media position was last updated."""
        return self.coordinator.last_update_success_time

    async def _async_call(
        self, action: Callable[..., Awaitable[Any]], *args: Any
    ) -> Any:
        """Call an API action, raise on failure and return the response."""
        try:
            return await action(*args)
        except AirlinoApiConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except AirlinoApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_error"
            ) from err

    @override
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse Home Assistant media sources."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media (URL or media source)."""
        if is_media_source_id(media_id):
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url
        elif media_type not in (
            MediaType.URL,
            MediaType.MUSIC,
        ) and not media_type.startswith("audio/"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="media_type_unsupported",
                translation_placeholders={"media_type": media_type},
            )
        elif not _is_valid_media_url(media_id):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="media_url_invalid",
                translation_placeholders={"media_id": media_id},
            )

        media_id = async_process_play_media_url(self.hass, media_id)

        _LOGGER.debug("Playing media on AirLino")
        await self._async_call(self.coordinator.api.async_play_station, media_id)
        await self.coordinator.async_request_refresh()

    async def _async_is_playing(self) -> bool:
        """Return whether the device is playing, bypassing the cached state."""
        status = await self._async_call(self.coordinator.api.async_get_player_status)
        return status.get("state") == PLAYER_STATE_PLAYING

    @override
    async def async_media_play(self) -> None:
        """Start playback."""
        if await self._async_is_playing():
            return
        await self._async_call(self.coordinator.api.async_play)
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_pause(self) -> None:
        """Pause playback when it is currently playing."""
        # The device only offers a toggle, so pausing must not resume playback.
        if not await self._async_is_playing():
            return
        await self._async_call(self.coordinator.api.async_playpause)
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_play_pause(self) -> None:
        """Toggle between play and pause."""
        await self._async_call(self.coordinator.api.async_playpause)
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self._async_call(self.coordinator.api.async_stop)
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_next_track(self) -> None:
        """Play next track."""
        await self._async_call(self.coordinator.api.async_next)
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_previous_track(self) -> None:
        """Play previous track."""
        await self._async_call(self.coordinator.api.async_previous)
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level (0.0 - 1.0)."""
        await self._async_call(
            self.coordinator.api.async_set_master_volume,
            round(volume * VOLUME_MAX),
        )
        await self.coordinator.async_request_refresh()

    @override
    async def async_volume_up(self) -> None:
        """Increase the volume."""
        await self._async_call(self.coordinator.api.async_volume_up)
        await self.coordinator.async_request_refresh()

    @override
    async def async_volume_down(self) -> None:
        """Decrease the volume."""
        await self._async_call(self.coordinator.api.async_volume_down)
        await self.coordinator.async_request_refresh()
