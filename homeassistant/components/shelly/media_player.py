"""Media player for Shelly."""

from __future__ import annotations

from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SLEEP_PERIOD
from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .entity import ShellyRpcEntity
from .utils import get_device_entry_gen

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up media player for Shelly devices."""
    if get_device_entry_gen(config_entry) not in RPC_GENERATIONS:
        return

    coordinator = config_entry.runtime_data.rpc
    assert coordinator

    if "media" not in coordinator.device.status:
        return

    if config_entry.data[CONF_SLEEP_PERIOD]:
        return

    async_add_entities([ShellyRpcMediaPlayer(coordinator)])


class ShellyRpcMediaPlayer(ShellyRpcEntity, MediaPlayerEntity):
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

    def __init__(self, coordinator: ShellyRpcCoordinator) -> None:
        """Initialize Shelly RPC media player."""
        super().__init__(coordinator, "media")

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

        return volume / 10

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        return self.status["playback"].get("media_meta", {}).get("title")

    @property
    def media_image_url(self) -> str | None:
        """Return the image URL of current playing media."""
        return self.status["playback"].get("media_meta", {}).get("thumb")

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
