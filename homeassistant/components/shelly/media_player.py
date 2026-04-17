"""Media player for Shelly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, cast

from aioshelly.const import RPC_GENERATIONS

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

from .const import DOMAIN
from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    async_setup_entry_rpc,
)
from .utils import get_device_entry_gen

CONTENT_TYPE_LOCAL_AUDIO = "local_audio"
CONTENT_TYPE_LOCAL_RADIO = "local_radio"

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
    if get_device_entry_gen(config_entry) not in RPC_GENERATIONS:
        return None

    return _async_setup_rpc_entry(hass, config_entry, async_add_entities)


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
        if title := self.status["playback"]["media_meta"].get("title"):
            return cast(str, title)

        return None

    @property
    def media_artist(self) -> str | None:
        """Return the artist of current playing media."""
        if artist := self.status["playback"]["media_meta"].get("artist"):
            return cast(str, artist)

        return None

    @property
    def media_album_name(self) -> str | None:
        """Return the album name of current playing media."""
        if album := self.status["playback"]["media_meta"].get("album"):
            return cast(str, album)

        return None

    @property
    def media_image_url(self) -> str | None:
        """Return the image URL of current playing media."""
        if (
            thumb := self.status["playback"]["media_meta"].get("thumb")
        ) and thumb.startswith("http"):
            return cast(str, thumb)

        return None

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.call_rpc("Media.MediaPlayer.Play", {})

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.call_rpc("Media.MediaPlayer.Pause", {})

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.call_rpc("Media.MediaPlayer.Stop", {})

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.call_rpc("Media.MediaPlayer.Next", {})

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.call_rpc("Media.MediaPlayer.Previous", {})

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.call_rpc("Media.SetVolume", {"volume": volume * 10})

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse radio stations and audio files."""
        if not media_content_id:
            return await self._async_browse_media_root()

        if media_content_id == CONTENT_TYPE_LOCAL_RADIO:
            return await self._async_browse_radio_stations(expanded=True)
        if media_content_id == CONTENT_TYPE_LOCAL_AUDIO:
            return await self._async_browse_local_audio(expanded=True)

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unsupported_media_content_type",
            translation_placeholders={"media_content_type": str(media_content_type)},
        )

    async def _async_browse_media_root(self) -> BrowseMedia:
        """Return root BrowseMedia tree."""
        return BrowseMedia(
            title="Local media",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            media_content_id="",
            children=[
                await self._async_browse_radio_stations(),
                await self._async_browse_local_audio(),
            ],
            can_play=False,
            can_expand=True,
        )

    async def _async_browse_local_audio(self, expanded: bool = False) -> BrowseMedia:
        """Return BrowseMedia tree for local audio files."""
        if expanded:
            result: dict[str, Any] = await self.coordinator.device.call_rpc(
                "Media.List", {}
            )
            children: list[BrowseMedia] | None = [
                BrowseMedia(
                    title=item["title"],
                    media_class=MediaClass.MUSIC,
                    media_content_type=CONTENT_TYPE_LOCAL_AUDIO,
                    media_content_id=str(item["id"]),
                    thumbnail=item["preview"],
                    can_play=True,
                    can_expand=False,
                )
                for item in result["list"]
                if item.get("type") == "AUDIO"
            ]
        else:
            children = None

        return BrowseMedia(
            title="Audio files",
            media_class=MediaClass.DIRECTORY,
            media_content_type=CONTENT_TYPE_LOCAL_AUDIO,
            media_content_id=CONTENT_TYPE_LOCAL_AUDIO,
            children_media_class=MediaClass.MUSIC,
            children=children,
            can_play=False,
            can_expand=True,
        )

    async def _async_browse_radio_stations(self, expanded: bool = False) -> BrowseMedia:
        """Return BrowseMedia tree for radio stations."""
        if expanded:
            result: dict[str, Any] = await self.coordinator.device.call_rpc(
                "Media.Radio.ListFavourites", {}
            )
            children: list[BrowseMedia] | None = [
                BrowseMedia(
                    title=station["name"],
                    media_class=MediaClass.MUSIC,
                    media_content_type=CONTENT_TYPE_LOCAL_RADIO,
                    media_content_id=str(station["id"]),
                    thumbnail=station["icon"],
                    can_play=True,
                    can_expand=False,
                )
                for station in result["list"]
            ]
        else:
            children = None

        return BrowseMedia(
            title="Radio stations",
            media_class=MediaClass.DIRECTORY,
            media_content_type=CONTENT_TYPE_LOCAL_RADIO,
            media_content_id=CONTENT_TYPE_LOCAL_RADIO,
            children_media_class=MediaClass.MUSIC,
            children=children,
            can_play=False,
            can_expand=True,
        )

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Play media by type and id."""
        if media_type == CONTENT_TYPE_LOCAL_RADIO:
            await self.call_rpc("Media.Radio.PlayFavourite", {"id": int(media_id)})
            return

        if media_type == CONTENT_TYPE_LOCAL_AUDIO:
            await self.call_rpc("Media.MediaPlayer.Play", {"id": int(media_id)})
            return

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="unsupported_media_type",
            translation_placeholders={"media_type": media_type},
        )
