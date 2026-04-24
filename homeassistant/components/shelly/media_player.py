"""Media player for Shelly."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import datetime
import hashlib
from typing import Any, Final, cast

from aioshelly.const import RPC_GENERATIONS
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    async_setup_entry_rpc,
    rpc_call,
)
from .utils import get_device_entry_gen

CONTENT_TYPE_AUDIO = "audio"
CONTENT_TYPE_RADIO = "radio"

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RpcMediaPlayerDescription(RpcEntityDescription, MediaPlayerEntityDescription):
    """Class to describe a Shelly RPC media player entity."""


RPC_MEDIA_PLAYER_ENTITIES: Final = {
    "media": RpcMediaPlayerDescription(
        key="media",
        device_class=MediaPlayerDeviceClass.SPEAKER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media player for Shelly devices."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        return _async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return None


@callback
def _async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    async_setup_entry_rpc(
        hass,
        config_entry,
        async_add_entities,
        RPC_MEDIA_PLAYER_ENTITIES,
        ShellyRpcMediaPlayer,
    )


class ShellyRpcMediaPlayer(ShellyRpcAttributeEntity, MediaPlayerEntity):
    """Representation of a Shelly RPC media player entity."""

    _attr_name = None
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.PLAY_MEDIA
    )
    _attr_media_content_type = MediaType.MUSIC
    entity_description: RpcMediaPlayerDescription

    _last_media_position: int | None = None
    _last_media_position_updated_at: datetime.datetime | None = None

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcMediaPlayerDescription,
    ) -> None:
        """Initialize Shelly RPC media player."""
        super().__init__(coordinator, key, attribute, description)

    @property
    def _media_meta(self) -> dict[str, Any]:
        """Return the media metadata."""
        return cast(dict[str, Any], self.status["playback"].get("media_meta", {}))

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the media player."""
        if self.status["playback"]["buffering"]:
            return MediaPlayerState.BUFFERING

        if self.status["playback"]["enable"]:
            return MediaPlayerState.PLAYING

        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return the volume level of the media player (0..1)."""
        volume = self.status["playback"]["volume"]

        return cast(float, volume) / 10

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        if title := self._media_meta.get("title"):
            return cast(str, title)

        return None

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media."""
        if self.status["playback"].get("media_type") == "RADIO":
            return None

        if artist := self._media_meta.get("artist"):
            return cast(str, artist)

        return None

    @property
    def media_album_name(self) -> str | None:
        """Return the album name of current playing media."""
        if self.status["playback"].get("media_type") == "RADIO":
            return None

        if album := self._media_meta.get("album"):
            return cast(str, album)

        return None

    @property
    def media_duration(self) -> int | None:
        """Return the duration of current playing media in seconds."""
        if self.status["playback"].get("media_type") == "RADIO":
            return None

        if (duration := self._media_meta.get("duration")) is not None:
            return cast(int, duration) // 1000

        return None

    @property
    def media_position(self) -> int | None:
        """Return the current playback position in seconds."""
        if (position := self._get_updated_media_position()) is not None:
            return position // 1000

        return None

    @property
    def media_position_updated_at(self) -> datetime.datetime | None:
        """Return when the position was last updated."""
        self._get_updated_media_position()

        return self._last_media_position_updated_at

    @property
    def media_image_url(self) -> str | None:
        """Return the image URL of current playing media."""
        if (thumb := self._media_meta.get("thumb")) and thumb.startswith("http"):
            return cast(str, thumb)

        return None

    @property
    def media_image_remotely_accessible(self) -> bool:
        """Return True if the image URL is remotely accessible."""
        return self.media_image_url is not None

    @property
    def media_image_hash(self) -> str | None:
        """Hash value for media image."""
        if (thumb := self._media_meta.get("thumb")) and thumb.startswith("data"):
            return hashlib.sha256(thumb.encode("utf-8")).hexdigest()[:16]
        return super().media_image_hash

    def _get_updated_media_position(self) -> int | None:
        """Return the current playback position and update its timestamp."""
        if (position := self._media_meta.get("position")) is None:
            self._last_media_position = None
            self._last_media_position_updated_at = None
            return None

        current_position = cast(int, position)
        if current_position != self._last_media_position:
            self._last_media_position = current_position
            self._last_media_position_updated_at = dt_util.utcnow()

        return current_position

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch media image of current playing track."""
        thumb = self._media_meta["thumb"]
        try:
            prefix, image_data = thumb.split(",", 1)
            image = base64.b64decode(image_data, validate=True)
            mime = prefix.split(";", 1)[0].rsplit(":", 1)[-1]
        except binascii.Error, ValueError:
            return await super().async_get_media_image()

        return image, mime

    @rpc_call
    async def async_media_play(self) -> None:
        """Send play command."""
        if self.state != MediaPlayerState.PLAYING:
            await self.coordinator.device.media_play_or_pause()

    @rpc_call
    async def async_media_pause(self) -> None:
        """Send pause command."""
        if self.state == MediaPlayerState.PLAYING:
            await self.coordinator.device.media_play_or_pause()

    @rpc_call
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.coordinator.device.media_stop()

    @rpc_call
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.device.media_next()

    @rpc_call
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.device.media_previous()

    @rpc_call
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.coordinator.device.media_set_volume(round(volume * 10))

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse radio stations and audio files."""
        if not media_content_type:
            return await self._async_browse_media_root()

        try:
            if media_content_type == CONTENT_TYPE_RADIO:
                return await self._async_browse_radio_stations(expanded=True)
            if media_content_type == CONTENT_TYPE_AUDIO:
                return await self._async_browse_audio_files(expanded=True)
        except DeviceConnectionError as err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_communication_action_error",
                translation_placeholders={
                    "entity": self.entity_id,
                    "device": self.coordinator.name,
                },
            ) from err
        except RpcCallError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rpc_call_action_error",
                translation_placeholders={
                    "entity": self.entity_id,
                    "device": self.coordinator.name,
                },
            ) from err
        except InvalidAuthError as err:
            await self.coordinator.async_shutdown_device_and_start_reauth()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={
                    "device": self.coordinator.name,
                },
            ) from err

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unsupported_media_content_type",
            translation_placeholders={"media_content_type": str(media_content_type)},
        )

    async def _async_browse_media_root(self) -> BrowseMedia:
        """Return root BrowseMedia tree."""
        return BrowseMedia(
            title="Shelly",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            media_content_id="",
            children=[
                await self._async_browse_radio_stations(),
                await self._async_browse_audio_files(),
            ],
            can_play=False,
            can_expand=True,
        )

    async def _async_browse_audio_files(self, expanded: bool = False) -> BrowseMedia:
        """Return BrowseMedia tree for audio files."""
        if expanded:
            result: list[
                dict[str, Any]
            ] = await self.coordinator.device.media_list_media()
            children: list[BrowseMedia] | None = [
                BrowseMedia(
                    title=item["title"],
                    media_class=MediaClass.MUSIC,
                    media_content_type=CONTENT_TYPE_AUDIO,
                    media_content_id=str(item["id"]),
                    thumbnail=item["preview"],
                    can_play=True,
                    can_expand=False,
                )
                for item in result
                if item["type"] == "AUDIO"
            ]
        else:
            children = None

        return BrowseMedia(
            title="Audio files",
            media_class=MediaClass.DIRECTORY,
            media_content_type=CONTENT_TYPE_AUDIO,
            media_content_id=CONTENT_TYPE_AUDIO,
            children_media_class=MediaClass.MUSIC,
            children=children,
            can_play=False,
            can_expand=True,
        )

    async def _async_browse_radio_stations(self, expanded: bool = False) -> BrowseMedia:
        """Return BrowseMedia tree for radio stations."""
        if expanded:
            result: list[
                dict[str, Any]
            ] = await self.coordinator.device.media_list_radio_stations()
            children: list[BrowseMedia] | None = [
                BrowseMedia(
                    title=station["name"],
                    media_class=MediaClass.MUSIC,
                    media_content_type=CONTENT_TYPE_RADIO,
                    media_content_id=str(station["id"]),
                    thumbnail=station["icon"],
                    can_play=True,
                    can_expand=False,
                )
                for station in result
            ]
        else:
            children = None

        return BrowseMedia(
            title="Radio stations",
            media_class=MediaClass.DIRECTORY,
            media_content_type=CONTENT_TYPE_RADIO,
            media_content_id=CONTENT_TYPE_RADIO,
            children_media_class=MediaClass.MUSIC,
            children=children,
            can_play=False,
            can_expand=True,
        )

    @rpc_call
    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Play media by type and id."""
        if media_id.isdecimal() is False:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unsupported_media_id",
                translation_placeholders={"media_id": media_id},
            )

        if media_type == CONTENT_TYPE_RADIO:
            await self.coordinator.device.media_play_radio_station(int(media_id))
            return

        if media_type == CONTENT_TYPE_AUDIO:
            await self.coordinator.device.media_play_media(int(media_id))
            return

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unsupported_media_type",
            translation_placeholders={"media_type": str(media_type)},
        )
