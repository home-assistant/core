"""Media player platform for the Yoto integration."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from yoto_api import Card, PlaybackStatus, YotoError, YotoPlayer

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 0

# Yoto players expose 16 hardware volume steps.
VOLUME_STEP = 1 / 16

PLAYBACK_STATE_MAP = {
    PlaybackStatus.PLAYING: MediaPlayerState.PLAYING,
    PlaybackStatus.PAUSED: MediaPlayerState.PAUSED,
    PlaybackStatus.STOPPED: MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto media player platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        YotoMediaPlayer(coordinator, player)
        for player in coordinator.client.players.values()
    )


class YotoMediaPlayer(YotoEntity, MediaPlayerEntity):
    """Representation of a Yoto Player."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_media_image_remotely_accessible = True
    _attr_volume_step = VOLUME_STEP
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.SEEK
    )

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator, player)
        self._attr_unique_id = player.id

    @property
    def available(self) -> bool:
        """Return whether the player is reachable through the Yoto cloud."""
        return super().available and bool(self.player.status.is_online)

    @property
    def state(self) -> MediaPlayerState:
        """Return the playback state."""
        status = self.player.last_event.playback_status
        if status is None:
            return MediaPlayerState.IDLE
        return PLAYBACK_STATE_MAP.get(status, MediaPlayerState.IDLE)

    @property
    def volume_level(self) -> float | None:
        """Return the current volume level."""
        return self.player.last_event.volume_percentage

    @property
    def media_duration(self) -> int | None:
        """Return the current track duration in seconds."""
        return self.player.last_event.track_length

    @property
    def media_position(self) -> int | None:
        """Return the current playback position in seconds."""
        return self.player.last_event.position

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Return the time the media position was last refreshed."""
        return self.player.last_event_received_at

    @property
    def media_title(self) -> str | None:
        """Return the title of the currently playing track."""
        event = self.player.last_event
        return event.track_title or event.chapter_title

    @property
    def media_album_name(self) -> str | None:
        """Return the title of the active card."""
        card = self._current_card()
        return card.title if card else None

    @property
    def media_artist(self) -> str | None:
        """Return the author of the active card."""
        card = self._current_card()
        return card.author if card else None

    @property
    def media_image_url(self) -> str | None:
        """Return the cover image URL of the active card."""
        card = self._current_card()
        return card.cover_image_large if card else None

    def _current_card(self) -> Card | None:
        """Return the cached library card for the currently active media."""
        card_id = self.player.last_event.card_id
        if not card_id:
            return None
        return self.coordinator.client.library.get(card_id)

    async def async_media_play(self) -> None:
        """Resume playback."""
        await self._async_run(self.coordinator.client.resume, self._player_id)

    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self._async_run(self.coordinator.client.pause, self._player_id)

    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self._async_run(self.coordinator.client.stop, self._player_id)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the playback volume (0.0 - 1.0)."""
        await self._async_run(
            self.coordinator.client.set_volume,
            self._player_id,
            round(volume * 100),
        )

    async def async_media_seek(self, position: float) -> None:
        """Seek to ``position`` seconds in the active track."""
        await self._async_run(
            self.coordinator.client.seek, self._player_id, int(position)
        )

    async def async_media_next_track(self) -> None:
        """Skip to the next track on the active card."""
        await self._async_run(self.coordinator.client.next_track, self._player_id)

    async def async_media_previous_track(self) -> None:
        """Skip to the previous track on the active card."""
        await self._async_run(self.coordinator.client.previous_track, self._player_id)

    async def _async_run(
        self, func: Callable[..., Awaitable[Any]], /, *args: Any
    ) -> None:
        """Await a Yoto command and surface failures as HA errors."""
        try:
            await func(*args)
        except YotoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
