"""Media player platform for the Yoto integration."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from yoto_api import YotoError, YotoPlayer
from yoto_api.Card import Card

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 0

# Yoto players expose 16 hardware volume steps.
VOLUME_STEPS = 16

PLAYBACK_STATE_MAP = {
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
    "stopped": MediaPlayerState.IDLE,
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
        for player in coordinator.yoto_manager.players.values()
    )


class YotoMediaPlayer(YotoEntity, MediaPlayerEntity):
    """Representation of a Yoto Player."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_media_image_remotely_accessible = True
    _attr_volume_step = 1 / VOLUME_STEPS
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PLAY_MEDIA
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
    def state(self) -> MediaPlayerState:
        """Return the playback state."""
        if not self.player.online:
            return MediaPlayerState.OFF
        if self.player.playback_status in PLAYBACK_STATE_MAP:
            return PLAYBACK_STATE_MAP[self.player.playback_status]
        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return the current volume level."""
        if self.player.volume is None:
            return None
        return self.player.volume / VOLUME_STEPS

    @property
    def media_duration(self) -> int | None:
        """Return the current track duration in seconds."""
        return self.player.track_length

    @property
    def media_position(self) -> int | None:
        """Return the current playback position in seconds."""
        return self.player.track_position

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Return the time the media position was last refreshed."""
        if self.player.track_position is None:
            return None
        return self.player.last_updated_at

    @property
    def media_title(self) -> str | None:
        """Return the title of the current chapter or track."""
        if self.player.chapter_title and self.player.track_title:
            if self.player.chapter_title == self.player.track_title:
                return self.player.chapter_title
            return f"{self.player.chapter_title} - {self.player.track_title}"
        return self.player.chapter_title or self.player.track_title

    def _current_card(self) -> Card | None:
        """Return the cached library card for the currently active media."""
        card_id = self.player.card_id
        if not card_id:
            return None
        return self.coordinator.yoto_manager.library.get(card_id)

    @property
    def media_artist(self) -> str | None:
        """Return the author of the active card."""
        card = self._current_card()
        return card.author if card else None

    @property
    def media_album_name(self) -> str | None:
        """Return the title of the active card."""
        card = self._current_card()
        return card.title if card else None

    @property
    def media_image_url(self) -> str | None:
        """Return the cover image URL of the active card."""
        card = self._current_card()
        return card.cover_image_large if card else None

    async def async_media_play(self) -> None:
        """Resume playback."""
        await self._async_run(
            self.coordinator.yoto_manager.resume_player, self._player_id
        )

    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self._async_run(
            self.coordinator.yoto_manager.pause_player, self._player_id
        )

    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self._async_run(
            self.coordinator.yoto_manager.stop_player, self._player_id
        )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the playback volume (0.0 - 1.0)."""
        await self._async_run(
            self.coordinator.yoto_manager.set_volume,
            self._player_id,
            int(round(volume * 100)),
        )

    async def async_media_seek(self, position: float) -> None:
        """Seek to ``position`` seconds in the active track."""
        await self._async_run(
            self.coordinator.yoto_manager.seek,
            self._player_id,
            int(position),
        )

    async def async_media_next_track(self) -> None:
        """Skip to the next track on the active card."""
        await self._async_run(self.coordinator.yoto_manager.next_track, self._player_id)

    async def async_media_previous_track(self) -> None:
        """Skip to the previous track on the active card."""
        await self._async_run(
            self.coordinator.yoto_manager.previous_track, self._player_id
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a Yoto card by id.

        ``media_id`` accepts either a bare card id or
        ``"<card_id>+<chapter_key>+<track_key>+<seconds_in>"``. Extra fields
        are optional and may be left empty.
        """
        card_id, chapter_key, track_key, seconds_in = _parse_media_id(media_id)
        await self._async_run(
            self.coordinator.yoto_manager.play_card,
            self._player_id,
            card_id,
            seconds_in,
            None,
            chapter_key,
            track_key,
        )

    async def _async_run(self, func: Callable[..., Any], /, *args: Any) -> None:
        """Run a Yoto command in the executor and propagate failures."""
        try:
            await self.hass.async_add_executor_job(func, *args)
        except YotoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.coordinator.async_request_refresh()


def _parse_media_id(media_id: str) -> tuple[str, str | None, str | None, int | None]:
    """Split a Yoto play_media id into its components."""
    parts = media_id.split("+")
    parts.extend([""] * (4 - len(parts)))
    card_id, chapter_key, track_key, seconds_raw = parts[:4]
    if seconds_raw:
        try:
            seconds_in: int | None = int(seconds_raw)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_media_id",
                translation_placeholders={"media_id": media_id},
            ) from err
    else:
        seconds_in = None
    return card_id, chapter_key or None, track_key or None, seconds_in
