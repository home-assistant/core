"""Support for ESPHome media players."""

from functools import partial
import logging
from typing import Any, override
from urllib.parse import urlparse

from aioesphomeapi import (
    EntityInfo,
    MediaPlayerCommand,
    MediaPlayerEntityFeature as EspMediaPlayerEntityFeature,
    MediaPlayerEntityState,
    MediaPlayerFormatPurpose,
    MediaPlayerInfo,
    MediaPlayerState as EspMediaPlayerState,
    MediaPlayerSupportedFormat,
)

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EXTRA,
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
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    esphome_float_state_property,
    esphome_state_property,
    platform_async_setup_entry,
)
from .enum_mapper import EsphomeEnumMapper
from .ffmpeg_proxy import async_create_proxy_url

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

_STATES: EsphomeEnumMapper[EspMediaPlayerState, MediaPlayerState] = EsphomeEnumMapper(
    {
        EspMediaPlayerState.IDLE: MediaPlayerState.IDLE,
        EspMediaPlayerState.PLAYING: MediaPlayerState.PLAYING,
        EspMediaPlayerState.PAUSED: MediaPlayerState.PAUSED,
        EspMediaPlayerState.OFF: MediaPlayerState.OFF,
        EspMediaPlayerState.ON: MediaPlayerState.ON,
    }
)

# The native API has no commands for these flags, and the entity does not
# implement search
_UNSUPPORTED_FEATURES = (
    EspMediaPlayerEntityFeature.SEEK
    | EspMediaPlayerEntityFeature.PREVIOUS_TRACK
    | EspMediaPlayerEntityFeature.NEXT_TRACK
    | EspMediaPlayerEntityFeature.SELECT_SOURCE
    | EspMediaPlayerEntityFeature.SELECT_SOUND_MODE
    | EspMediaPlayerEntityFeature.SHUFFLE_SET
    | EspMediaPlayerEntityFeature.GROUPING
    | EspMediaPlayerEntityFeature.SEARCH_MEDIA
)

_FEATURES = {
    EspMediaPlayerEntityFeature.PAUSE: MediaPlayerEntityFeature.PAUSE,
    EspMediaPlayerEntityFeature.VOLUME_SET: MediaPlayerEntityFeature.VOLUME_SET,
    EspMediaPlayerEntityFeature.VOLUME_MUTE: MediaPlayerEntityFeature.VOLUME_MUTE,
    EspMediaPlayerEntityFeature.TURN_ON: MediaPlayerEntityFeature.TURN_ON,
    EspMediaPlayerEntityFeature.TURN_OFF: MediaPlayerEntityFeature.TURN_OFF,
    EspMediaPlayerEntityFeature.PLAY_MEDIA: MediaPlayerEntityFeature.PLAY_MEDIA,
    EspMediaPlayerEntityFeature.VOLUME_STEP: MediaPlayerEntityFeature.VOLUME_STEP,
    EspMediaPlayerEntityFeature.STOP: MediaPlayerEntityFeature.STOP,
    EspMediaPlayerEntityFeature.CLEAR_PLAYLIST: MediaPlayerEntityFeature.CLEAR_PLAYLIST,
    EspMediaPlayerEntityFeature.PLAY: MediaPlayerEntityFeature.PLAY,
    EspMediaPlayerEntityFeature.BROWSE_MEDIA: MediaPlayerEntityFeature.BROWSE_MEDIA,
    EspMediaPlayerEntityFeature.REPEAT_SET: MediaPlayerEntityFeature.REPEAT_SET,
    EspMediaPlayerEntityFeature.MEDIA_ANNOUNCE: MediaPlayerEntityFeature.MEDIA_ANNOUNCE,
    EspMediaPlayerEntityFeature.MEDIA_ENQUEUE: MediaPlayerEntityFeature.MEDIA_ENQUEUE,
}

ATTR_BYPASS_PROXY = "bypass_proxy"


class EsphomeMediaPlayer(
    EsphomeEntity[MediaPlayerInfo, MediaPlayerEntityState], MediaPlayerEntity
):
    """A media player implementation for esphome."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER

    @callback
    @override
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        esp_flags = (
            EspMediaPlayerEntityFeature(
                self._static_info.feature_flags_compat(self._api_version)
            )
            & ~_UNSUPPORTED_FEATURES
        )
        flags = MediaPlayerEntityFeature(0)
        for espflag in esp_flags:
            flags |= _FEATURES[espflag]
        self._attr_supported_features = flags
        self._entry_data.media_player_formats[self] = (
            self._static_info.supported_formats
        )

    @property
    @esphome_state_property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return current state."""
        return _STATES.from_esphome(self._state.state)

    @property
    @esphome_state_property
    @override
    def is_volume_muted(self) -> bool:
        """Return true if volume is muted."""
        return self._state.muted

    @property
    @esphome_float_state_property
    @override
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return self._state.volume

    @convert_api_error_ha_error
    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Send the play command with media url to the media player."""
        enqueue = kwargs.get(ATTR_MEDIA_ENQUEUE)
        # The device can only append to its playlist or replace it
        if enqueue in (MediaPlayerEnqueue.NEXT, MediaPlayerEnqueue.PLAY):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="enqueue_mode_not_supported",
                translation_placeholders={"enqueue": enqueue},
            )
        if media_source.is_media_source_id(media_id):
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url

        media_id = async_process_play_media_url(self.hass, media_id)
        announcement = kwargs.get(ATTR_MEDIA_ANNOUNCE)
        bypass_proxy = kwargs.get(ATTR_MEDIA_EXTRA, {}).get(ATTR_BYPASS_PROXY)
        supported_formats = self._entry_data.media_player_formats.get(self)

        if (
            not bypass_proxy
            and supported_formats
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
            command=(
                MediaPlayerCommand.ENQUEUE
                if enqueue == MediaPlayerEnqueue.ADD
                else None
            ),
            media_url=media_id,
            announcement=announcement,
            device_id=self._static_info.device_id,
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Handle entity being removed."""
        await super().async_will_remove_from_hass()
        self._entry_data.media_player_formats.pop(self, None)

    def _get_proxy_url(
        self,
        supported_formats: list[MediaPlayerSupportedFormat],
        url: str,
        announcement: bool,
    ) -> str | None:
        """Get URL for ffmpeg proxy."""
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
        bitrate: int | None = None
        if format_to_use.sample_rate > 0:
            rate = format_to_use.sample_rate

        if format_to_use.num_channels > 0:
            channels = format_to_use.num_channels

        if format_to_use.sample_bytes > 0:
            width = format_to_use.sample_bytes

        if format_to_use.bitrate > 0:
            bitrate = format_to_use.bitrate

        proxy_url = async_create_proxy_url(
            self.hass,
            device_id,
            url,
            media_format=media_format,
            rate=rate,
            channels=channels,
            width=width,
            bitrate=bitrate,
        )

        # Resolve URL
        return async_process_play_media_url(self.hass, proxy_url)

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

    @convert_api_error_ha_error
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._client.media_player_command(
            self._key, volume=volume, device_id=self._static_info.device_id
        )

    @convert_api_error_ha_error
    @override
    async def async_volume_up(self) -> None:
        """Turn volume up."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.VOLUME_UP,
            device_id=self._static_info.device_id,
        )

    @convert_api_error_ha_error
    @override
    async def async_volume_down(self) -> None:
        """Turn volume down."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.VOLUME_DOWN,
            device_id=self._static_info.device_id,
        )

    @convert_api_error_ha_error
    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.PAUSE,
            device_id=self._static_info.device_id,
        )

    @convert_api_error_ha_error
    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.PLAY,
            device_id=self._static_info.device_id,
        )

    @convert_api_error_ha_error
    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.STOP,
            device_id=self._static_info.device_id,
        )

    @convert_api_error_ha_error
    @override
    async def async_clear_playlist(self) -> None:
        """Clear the playlist."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.CLEAR_PLAYLIST,
            device_id=self._static_info.device_id,
        )

    @convert_api_error_ha_error
    @override
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set the repeat mode."""
        if repeat == RepeatMode.ALL:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="repeat_mode_not_supported",
                translation_placeholders={"repeat_mode": repeat},
            )
        self._client.media_player_command(
            self._key,
            command=(
                MediaPlayerCommand.REPEAT_ONE
                if repeat == RepeatMode.ONE
                else MediaPlayerCommand.REPEAT_OFF
            ),
            device_id=self._static_info.device_id,
        )
        # The device does not report its repeat mode
        self._attr_repeat = repeat
        self.async_write_ha_state()

    @convert_api_error_ha_error
    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.MUTE if mute else MediaPlayerCommand.UNMUTE,
            device_id=self._static_info.device_id,
        )

    @convert_api_error_ha_error
    @override
    async def async_turn_on(self) -> None:
        """Send turn on command."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.TURN_ON,
            device_id=self._static_info.device_id,
        )

    @convert_api_error_ha_error
    @override
    async def async_turn_off(self) -> None:
        """Send turn off command."""
        self._client.media_player_command(
            self._key,
            command=MediaPlayerCommand.TURN_OFF,
            device_id=self._static_info.device_id,
        )


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
