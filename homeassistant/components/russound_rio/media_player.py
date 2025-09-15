"""Support for Russound multizone controllers using RIO Protocol."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import TYPE_CHECKING, Any

from aiorussound import Controller
from aiorussound.const import FeatureFlag
from aiorussound.models import PlayStatus, Source
from aiorussound.util import is_feature_supported

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RussoundConfigEntry, media_browser
from .const import DOMAIN, RUSSOUND_MEDIA_TYPE_PRESET, SELECT_SOURCE_DELAY
from .entity import RussoundBaseEntity, command

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Russound RIO platform."""
    client = entry.runtime_data
    sources = client.sources

    async_add_entities(
        RussoundZoneDevice(controller, zone_id, sources)
        for controller in client.controllers.values()
        for zone_id in controller.zones
    )


def _parse_preset_source_id(media_id: str) -> tuple[int | None, int]:
    source_id = None
    if "," in media_id:
        source_id_str, preset_id_str = media_id.split(",", maxsplit=1)
        source_id = int(source_id_str.strip())
        preset_id = int(preset_id_str.strip())
    else:
        preset_id = int(media_id)
    return source_id, preset_id


class RussoundZoneDevice(RussoundBaseEntity, MediaPlayerEntity):
    """Representation of a Russound Zone."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SEEK
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )
    _attr_name = None

    def __init__(
        self, controller: Controller, zone_id: int, sources: dict[int, Source]
    ) -> None:
        """Initialize the zone device."""
        super().__init__(controller, zone_id)
        _zone = self._zone
        self._sources = sources
        self._attr_unique_id = f"{self._primary_mac_address}-{_zone.device_str}"

    @property
    def _source(self) -> Source:
        return self._zone.fetch_current_source()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        status = self._zone.status
        play_status = self._source.play_status
        if not status:
            return MediaPlayerState.OFF
        if play_status == PlayStatus.PLAYING:
            return MediaPlayerState.PLAYING
        if play_status == PlayStatus.PAUSED:
            return MediaPlayerState.PAUSED
        if play_status == PlayStatus.TRANSITIONING:
            return MediaPlayerState.BUFFERING
        if play_status == PlayStatus.STOPPED:
            return MediaPlayerState.IDLE
        return MediaPlayerState.ON

    @property
    def source(self) -> str:
        """Get the currently selected source."""
        return self._source.name

    @property
    def source_list(self) -> list[str]:
        """Return a list of available input sources."""
        if TYPE_CHECKING:
            assert self._client.rio_version
        available_sources = (
            [
                source
                for source_id, source in self._sources.items()
                if source_id in self._zone.enabled_sources
            ]
            if is_feature_supported(
                self._client.rio_version, FeatureFlag.SUPPORT_ZONE_SOURCE_EXCLUSION
            )
            else self._sources.values()
        )
        return [x.name for x in available_sources]

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._source.song_name or self._source.channel

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self._source.artist_name

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self._source.album_name

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self._source.cover_art_url

    @property
    def media_duration(self) -> int | None:
        """Duration of the current media."""
        return self._source.track_time

    @property
    def media_position(self) -> int | None:
        """Position of the current media."""
        return self._source.play_time

    @property
    def media_position_updated_at(self) -> dt.datetime:
        """Last time the media position was updated."""
        return self._source.position_last_updated

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1).

        Value is returned based on a range (0..50).
        Therefore float divide by 50 to get to the required range.
        """
        return self._zone.volume / 50.0

    @property
    def is_volume_muted(self) -> bool:
        """Return whether zone is muted."""
        return self._zone.is_mute

    @command
    async def async_turn_off(self) -> None:
        """Turn off the zone."""
        await self._zone.zone_off()

    @command
    async def async_turn_on(self) -> None:
        """Turn on the zone."""
        await self._zone.zone_on()

    @command
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        rvol = int(volume * 50.0)
        await self._zone.set_volume(str(rvol))

    @command
    async def async_select_source(self, source: str) -> None:
        """Select the source input for this zone."""
        for source_id, src in self._sources.items():
            if src.name.lower() != source.lower():
                continue
            await self._zone.select_source(source_id)
            break

    @command
    async def async_volume_up(self) -> None:
        """Step the volume up."""
        await self._zone.volume_up()

    @command
    async def async_volume_down(self) -> None:
        """Step the volume down."""
        await self._zone.volume_down()

    @command
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the media player."""
        if FeatureFlag.COMMANDS_ZONE_MUTE_OFF_ON in self._client.supported_features:
            if mute:
                await self._zone.mute()
            else:
                await self._zone.unmute()
            return

        if mute != self.is_volume_muted:
            await self._zone.toggle_mute()

    @command
    async def async_media_seek(self, position: float) -> None:
        """Seek to a position in the current media."""
        await self._zone.set_seek_time(int(position))

    @command
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media on the Russound zone."""

        if media_type != RUSSOUND_MEDIA_TYPE_PRESET:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unsupported_media_type",
                translation_placeholders={
                    "media_type": media_type,
                },
            )

        try:
            source_id, preset_id = _parse_preset_source_id(media_id)
        except ValueError as ve:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="preset_non_integer",
                translation_placeholders={"preset_id": media_id},
            ) from ve
        if source_id:
            await self._zone.select_source(source_id)
            await asyncio.sleep(SELECT_SOURCE_DELAY)
        if not self._source.presets or preset_id not in self._source.presets:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="missing_preset",
                translation_placeholders={"preset_id": media_id},
            )
        await self._zone.restore_preset(preset_id)

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the media browsing helper."""
        return await media_browser.async_browse_media(
            self.hass, self._client, media_content_id, media_content_type, self._zone
        )
