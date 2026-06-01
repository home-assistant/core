"""Media player platform for the Yoto integration."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from yoto_api import Card, Chapter, PlaybackStatus, Track, YotoError, YotoPlayer

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
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

URI_SCHEME = "yoto"
# The URI authority ("card") names the content type. Only cards exist today;
# reserving it leaves room for groups without breaking URIs.
URI_CARD = "card"

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
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
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

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a Yoto card, chapter, or track from the browse tree."""
        try:
            card_id, chapter_key, track_key = _parse_uri(media_id)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_media_id",
                translation_placeholders={"media_id": media_id},
            ) from err

        client = self.coordinator.client
        card = client.library.get(card_id)
        if card is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_card",
                translation_placeholders={"card_id": card_id},
            )

        if chapter_key is not None:
            # Library list may not include chapters yet; fetch detail on demand.
            if not card.chapters:
                try:
                    await client.update_card_detail(card_id)
                except YotoError as err:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="card_detail_failed",
                        translation_placeholders={"error": str(err)},
                    ) from err

            chapter = card.chapters.get(chapter_key)
            if chapter is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_chapter",
                    translation_placeholders={
                        "chapter_key": chapter_key,
                        "card_id": card_id,
                    },
                )
            if track_key is not None and track_key not in chapter.tracks:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_track",
                    translation_placeholders={
                        "track_key": track_key,
                        "card_id": card_id,
                    },
                )
            # A chapter plays from its first track.
            if track_key is None and chapter.tracks:
                track_key = next(iter(chapter.tracks))

        # Targeted chapter/track plays start at 0; a card play keeps its resume point.
        seconds_in = 0 if chapter_key is not None else None
        try:
            await client.play_card(
                self._player_id,
                card_id,
                chapter_key=chapter_key,
                track_key=track_key,
                seconds_in=seconds_in,
            )
        except YotoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="play_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse the Yoto card library."""
        if not media_content_id:
            return self._browse_root()

        try:
            card_id, chapter_key, _ = _parse_uri(media_content_id)
        except ValueError as err:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="invalid_media_id",
                translation_placeholders={"media_id": media_content_id},
            ) from err

        card = self.coordinator.client.library.get(card_id)
        if card is None:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="unknown_card",
                translation_placeholders={"card_id": card_id},
            )

        if not card.chapters:
            try:
                await self.coordinator.client.update_card_detail(card_id)
            except YotoError as err:
                raise BrowseError(
                    translation_domain=DOMAIN,
                    translation_key="card_detail_failed",
                    translation_placeholders={"error": str(err)},
                ) from err

        if chapter_key is not None:
            chapter = card.chapters.get(chapter_key)
            if chapter is None:
                raise BrowseError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_chapter",
                    translation_placeholders={
                        "chapter_key": chapter_key,
                        "card_id": card_id,
                    },
                )
            return self._browse_chapter(card_id, chapter_key, chapter)

        return self._browse_card(card)

    def _browse_root(self) -> BrowseMedia:
        """List every card in the user's library."""
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type=MediaType.MUSIC,
            title="Yoto library",
            can_play=False,
            can_expand=True,
            children=[
                self._card_node(card)
                for card in self.coordinator.client.library.values()
            ],
            children_media_class=MediaClass.ALBUM,
        )

    def _browse_card(self, card: Card) -> BrowseMedia:
        """List a card's chapters, collapsing single-chapter cards to tracks."""
        chapters = card.chapters
        # Single-chapter cards expand straight to tracks (skip a one-item level).
        if len(chapters) == 1:
            chapter_key, chapter = next(iter(chapters.items()))
            children = [
                self._track_node(card.id, chapter_key, track_key, track)
                for track_key, track in chapter.tracks.items()
            ]
        else:
            children = [
                self._chapter_node(card.id, chapter_key, chapter)
                for chapter_key, chapter in chapters.items()
            ]
        node = self._card_node(card)
        node.children = children
        return node

    def _browse_chapter(
        self, card_id: str, chapter_key: str, chapter: Chapter
    ) -> BrowseMedia:
        """List the tracks of a chapter."""
        node = self._chapter_node(card_id, chapter_key, chapter)
        node.can_expand = True
        node.children = [
            self._track_node(card_id, chapter_key, track_key, track)
            for track_key, track in chapter.tracks.items()
        ]
        return node

    def _card_node(self, card: Card) -> BrowseMedia:
        """Build a browse node for a card."""
        # MUSIC (not ALBUM) so children render in list view with thumbnails.
        return BrowseMedia(
            media_class=MediaClass.MUSIC,
            media_content_id=_build_uri(card.id),
            media_content_type=MediaType.MUSIC,
            title=card.title or card.id,
            can_play=True,
            can_expand=True,
            thumbnail=card.cover_image_large,
        )

    def _chapter_node(
        self, card_id: str, chapter_key: str, chapter: Chapter
    ) -> BrowseMedia:
        """Build a browse node for a chapter."""
        # Single-track chapters aren't expandable: click plays the track.
        return BrowseMedia(
            media_class=MediaClass.MUSIC,
            media_content_id=_build_uri(card_id, chapter_key),
            media_content_type=MediaType.MUSIC,
            title=chapter.title or chapter_key,
            can_play=True,
            can_expand=len(chapter.tracks) > 1,
            thumbnail=chapter.icon,
        )

    def _track_node(
        self, card_id: str, chapter_key: str, track_key: str, track: Track
    ) -> BrowseMedia:
        """Build a browse node for a track."""
        return BrowseMedia(
            media_class=MediaClass.MUSIC,
            media_content_id=_build_uri(card_id, chapter_key, track_key),
            media_content_type=MediaType.MUSIC,
            title=track.title or track_key,
            can_play=True,
            can_expand=False,
            thumbnail=track.icon,
        )

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


def _build_uri(
    card_id: str,
    chapter_key: str | None = None,
    track_key: str | None = None,
) -> str:
    """Build a yoto://card/... URI from card/chapter/track parts."""
    segments = [URI_CARD, card_id]
    if chapter_key is not None:
        segments.append(chapter_key)
        if track_key is not None:
            segments.append(track_key)
    return f"{URI_SCHEME}://{'/'.join(segments)}"


def _parse_uri(media_id: str) -> tuple[str, str | None, str | None]:
    """Parse a yoto://card/... URI into card/chapter/track parts.

    Parsed manually because URL parsers lower-case the authority and Yoto
    IDs are case-sensitive.
    """
    prefix = f"{URI_SCHEME}://{URI_CARD}/"
    if not media_id.startswith(prefix):
        raise ValueError(f"Not a Yoto media identifier: {media_id}")
    parts = media_id[len(prefix) :].split("/")
    if not parts or len(parts) > 3 or any(not segment for segment in parts):
        raise ValueError(f"Not a Yoto media identifier: {media_id}")
    card_id = parts[0]
    chapter_key = parts[1] if len(parts) > 1 else None
    track_key = parts[2] if len(parts) > 2 else None
    return card_id, chapter_key, track_key
