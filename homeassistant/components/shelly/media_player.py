"""Media player for Shelly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SLEEP_PERIOD
from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    async_setup_entry_rpc,
)
from .utils import get_device_entry_gen

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RpcMediaPlayerDescription(RpcEntityDescription, MediaPlayerEntityDescription):
    """Class to describe a Shelly RPC media player entity."""


RPC_MEDIA_PLAYER_ENTITIES: Final = {
    "media_player": RpcMediaPlayerDescription(
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

    if config_entry.data[CONF_SLEEP_PERIOD]:
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
        self._attr_unique_id = f"{coordinator.mac}-{key}"

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the media player."""
        if self.status["playback"]["enable"]:
            return MediaPlayerState.PLAYING

        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return the volume level of the media player (0..1)."""
        volume = self.status["playback"].get("volume")
        if volume is None:
            return None

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
