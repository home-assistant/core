"""Support for ESPHome media players."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any, cast
from urllib.parse import urlparse

from aioesphomeapi import (
    EntityInfo,
    MediaPlayerCommand,
    MediaPlayerEntityState,
    MediaPlayerFormatPurpose,
    MediaPlayerInfo,
    MediaPlayerState as EspMediaPlayerState,
    MediaPlayerSupportedFormat,
)

from homeassistant import util
from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ENQUEUE,
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.core import callback

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    esphome_float_state_property,
    esphome_state_property,
    platform_async_setup_entry,
)
from .enum_mapper import EsphomeEnumMapper
from .ffmpeg_proxy import async_create_proxy_url

_LOGGER = logging.getLogger(__name__)

_STATES: EsphomeEnumMapper[EspMediaPlayerState, MediaPlayerState] = EsphomeEnumMapper(
    {
        EspMediaPlayerState.IDLE: MediaPlayerState.IDLE,
        EspMediaPlayerState.PLAYING: MediaPlayerState.PLAYING,
        EspMediaPlayerState.PAUSED: MediaPlayerState.PAUSED,
        # mapping to PLAYING since core/component/media_player does
        # not have ANNOUNCING state
        EspMediaPlayerState.ANNOUNCING: MediaPlayerState.PLAYING,
        EspMediaPlayerState.OFF: MediaPlayerState.OFF,
        EspMediaPlayerState.ON: MediaPlayerState.ON,
    }
)


class EsphomeMediaPlayer(
    EsphomeEntity[MediaPlayerInfo, MediaPlayerEntityState], MediaPlayerEntity
):
    """A media player implementation for esphome."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        flags = (
            MediaPlayerEntityFeature.PLAY_MEDIA
            | MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
        )
        if self._static_info.supports_grouping:
            flags |= MediaPlayerEntityFeature.GROUPING

        if self._static_info.supports_pause:
            flags |= MediaPlayerEntityFeature.PAUSE | MediaPlayerEntityFeature.PLAY

        if self._static_info.supports_next_previous_track:
            flags |= (
                MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
                | MediaPlayerEntityFeature.CLEAR_PLAYLIST
            )
            flags |= (
                MediaPlayerEntityFeature.MEDIA_ENQUEUE
                | MediaPlayerEntityFeature.REPEAT_SET
                | MediaPlayerEntityFeature.SHUFFLE_SET
            )

        if self._static_info.supports_turn_off_on:
            flags |= (
                MediaPlayerEntityFeature.TURN_OFF | MediaPlayerEntityFeature.TURN_ON
            )
        self._attr_supported_features = flags
        self._entry_data.media_player_formats[static_info.unique_id] = cast(
            MediaPlayerInfo, static_info
        ).supported_formats

    @callback
    def _on_state_update(self) -> None:
        """Call when state changed."""
        self._attr_media_position_updated_at = util.dt.utcnow()
        super()._on_state_update()

    @property
    @esphome_state_property
    def state(self) -> MediaPlayerState | None:
        """Return current state."""
        return _STATES.from_esphome(self._state.state)

    @property
    @esphome_state_property
    def is_volume_muted(self) -> bool:
        """Return true if volume is muted."""
        return self._state.muted

    @property
    @esphome_float_state_property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self._state.volume

    @property
    @esphome_state_property
    def repeat(self) -> RepeatMode:
        """Repeat the song or playlist."""
        repeat = RepeatMode.OFF
        if self._state.repeat == "all":
            repeat = RepeatMode.ALL
        elif self._state.repeat == "one":
            repeat = RepeatMode.ONE
        return repeat

    @property
    @esphome_state_property
    def shuffle(self) -> bool:
        """Return true if set is shuffled."""
        return self._state.shuffle

    @property
    @esphome_state_property
    def media_artist(self) -> str | None:
        """Media artist."""
        return self._state.artist

    @property
    @esphome_state_property
    def media_album_artist(self) -> str | None:
        """Media album artist."""
        artist = self._attr_media_artist
        if len(self._state.artist) > 0:
            artist = self._state.artist
        return artist

    @property
    @esphome_state_property
    def media_album_name(self) -> str | None:
        """Media album name."""
        album = self._attr_media_album_name
        if len(self._state.album) > 0:
            album = self._state.album
        return album

    @property
    @esphome_state_property
    def media_title(self) -> str | None:
        """Media title."""
        title = self._attr_media_title
        if len(self._state.title) > 0:
            if len(self._state.artist) > 0:
                title = self._state.artist + ": " + self._state.title
            else:
                title = self._state.title
        return title

    @property
    @esphome_state_property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self._state.duration if self._state.duration > 0 else None

    @property
    @esphome_state_property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self._state.position if self._state.position > 0 else None

    @convert_api_error_ha_error
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play command with media url to the media player."""
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url

        media_id = async_process_play_media_url(self.hass, media_id)

        announcement = False
        enqueue = MediaPlayerEnqueue.REPLACE
        for key, value in kwargs.items():
            if key == ATTR_MEDIA_ANNOUNCE:
                announcement = value
            elif key == ATTR_MEDIA_ENQUEUE:
                enqueue = value

        supported_formats: list[MediaPlayerSupportedFormat] | None = (
            self._entry_data.media_player_formats.get(self._static_info.unique_id)
        )

        if (
            supported_formats
            and _is_url(media_id)
            and (
                proxy_url := self._get_proxy_url(
                    supported_formats, media_id, announcement is True
                )
            )
        ):
            # Substitute proxy URL
            media_id = proxy_url

        self._client.media_player_command(
            self._key,
            media_url=media_id,
            announcement=announcement,
            enqueue=enqueue,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity being removed."""
        await super().async_will_remove_from_hass()
        self._entry_data.media_player_formats.pop(self.entity_id, None)

    def _get_proxy_url(
        self,
        supported_formats: list[MediaPlayerSupportedFormat],
        url: str,
        announcement: bool,
    ) -> str | None:
        """Get URL for ffmpeg proxy."""
        if self.device_entry is None:
            # Device id is required
            return None

        # Choose the first default or announcement supported format
        format_to_use: MediaPlayerSupportedFormat | None = None
        for supported_format in supported_formats:
            if (format_to_use is None) and (
                supported_format.purpose == MediaPlayerFormatPurpose.DEFAULT
            ):
                # First default format
                format_to_use = supported_format
            elif announcement and (
                supported_format.purpose == MediaPlayerFormatPurpose.ANNOUNCEMENT
            ):
                # First announcement format
                format_to_use = supported_format
                break

        if format_to_use is None:
            # No format for conversion
            return None

        # Replace the media URL with a proxy URL pointing to Home
        # Assistant. When requested, Home Assistant will use ffmpeg to
        # convert the source URL to the supported format.
        _LOGGER.debug("Proxying media url %s with format %s", url, format_to_use)
        device_id = self.device_entry.id
        media_format = format_to_use.format

        # 0 = None
        rate: int | None = None
        channels: int | None = None
        width: int | None = None
        if format_to_use.sample_rate > 0:
            rate = format_to_use.sample_rate

        if format_to_use.num_channels > 0:
            channels = format_to_use.num_channels

        if format_to_use.sample_bytes > 0:
            width = format_to_use.sample_bytes

        proxy_url = async_create_proxy_url(
            self.hass,
            device_id,
            url,
            media_format=media_format,
            rate=rate,
            channels=channels,
            width=width,
        )

        # Resolve URL
        return async_process_play_media_url(self.hass, proxy_url)

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

    @convert_api_error_ha_error
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._client.media_player_command(self._key, volume=volume)

    @convert_api_error_ha_error
    async def async_media_pause(self) -> None:
        """Send pause command."""
        self._client.media_player_command(self._key, command=MediaPlayerCommand.PAUSE)

    @convert_api_error_ha_error
    async def async_media_play(self) -> None:
        """Send play command."""
        self._client.media_player_command(self._key, command=MediaPlayerCommand.PLAY)

    @convert_api_error_ha_error
    async def async_media_stop(self) -> None:
        """Send stop command."""
        self._client.media_player_command(self._key, command=MediaPlayerCommand.STOP)

    @convert_api_error_ha_error
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.MUTE if mute else MediaPlayerCommand.UNMUTE,
        )

    @convert_api_error_ha_error
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        self._client.media_player_command(
            self._key, command=MediaPlayerCommand.NEXT_TRACK
        )

    @convert_api_error_ha_error
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        self._client.media_player_command(
            self._key, command=MediaPlayerCommand.PREVIOUS_TRACK
        )

    @convert_api_error_ha_error
    async def async_clear_playlist(self) -> None:
        """Send clear playlist command."""
        self._client.media_player_command(
            self._key, command=MediaPlayerCommand.CLEAR_PLAYLIST
        )

    @convert_api_error_ha_error
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Send set shuffle command."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.SHUFFLE
            if shuffle
            else MediaPlayerCommand.UNSHUFFLE,
        )

    @convert_api_error_ha_error
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Send repeat set command."""
        repeatCmd = MediaPlayerCommand.REPEAT_OFF
        if repeat == RepeatMode.ONE:
            repeatCmd = MediaPlayerCommand.REPEAT_ONE
        elif repeat == RepeatMode.ALL:
            repeatCmd = MediaPlayerCommand.REPEAT_ALL

        self._client.media_player_command(self._key, command=repeatCmd)

    @convert_api_error_ha_error
    async def async_turn_on(self) -> None:
        """Send turn on command."""
        self._client.media_player_command(self._key, command=MediaPlayerCommand.TURN_ON)

    @convert_api_error_ha_error
    async def async_turn_off(self) -> None:
        """Send turn off command."""
        self._client.media_player_command(
            self._key, command=MediaPlayerCommand.TURN_OFF
        )

    @convert_api_error_ha_error
    async def async_join_players(self, group_members: list[str]) -> None:
        """Self will be leader of group and group_members who will be followers."""
        gms = ""
        for gm in group_members:
            gms = gms + gm + ","
        self._client.media_player_command(
            self._key, group_members=gms, command=MediaPlayerCommand.JOIN
        )

    @convert_api_error_ha_error
    async def async_unjoin_player(self) -> None:
        """Remove knowledge of self ability to publish and remove group_members as subscribers."""
        self._client.media_player_command(self._key, command=MediaPlayerCommand.UNJOIN)


def _is_url(url: str) -> bool:
    """Validate the URL can be parsed and at least has scheme + netloc."""
    result = urlparse(url)
    return all([result.scheme, result.netloc])


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=MediaPlayerInfo,
    entity_type=EsphomeMediaPlayer,
    state_type=MediaPlayerEntityState,
)
