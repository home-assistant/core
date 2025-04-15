"""Denon HEOS Media Player."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine, Sequence
from contextlib import suppress
import dataclasses
from datetime import datetime
from functools import reduce, wraps
import logging
from operator import ior
from typing import Any, Final

from pyheos import (
    AddCriteriaType,
    ControlType,
    HeosError,
    HeosPlayer,
    MediaItem,
    MediaMusicSource,
    MediaType as HeosMediaType,
    PlayState,
    RepeatType,
    const as heos_const,
)
from pyheos.util import mediauri as heos_source

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.components.media_source import BrowseMediaSource
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from . import services
from .const import DOMAIN as HEOS_DOMAIN
from .coordinator import HeosConfigEntry, HeosCoordinator

PARALLEL_UPDATES = 0

BROWSE_ROOT: Final = "heos://media"

BASE_SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.GROUPING
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.MEDIA_ENQUEUE
)

PLAY_STATE_TO_STATE = {
    None: MediaPlayerState.IDLE,
    PlayState.UNKNOWN: MediaPlayerState.IDLE,
    PlayState.PLAY: MediaPlayerState.PLAYING,
    PlayState.STOP: MediaPlayerState.IDLE,
    PlayState.PAUSE: MediaPlayerState.PAUSED,
}

CONTROL_TO_SUPPORT = {
    ControlType.PLAY: MediaPlayerEntityFeature.PLAY,
    ControlType.PAUSE: MediaPlayerEntityFeature.PAUSE,
    ControlType.STOP: MediaPlayerEntityFeature.STOP,
    ControlType.PLAY_PREVIOUS: MediaPlayerEntityFeature.PREVIOUS_TRACK,
    ControlType.PLAY_NEXT: MediaPlayerEntityFeature.NEXT_TRACK,
}

HA_HEOS_ENQUEUE_MAP = {
    None: AddCriteriaType.REPLACE_AND_PLAY,
    MediaPlayerEnqueue.ADD: AddCriteriaType.ADD_TO_END,
    MediaPlayerEnqueue.REPLACE: AddCriteriaType.REPLACE_AND_PLAY,
    MediaPlayerEnqueue.NEXT: AddCriteriaType.PLAY_NEXT,
    MediaPlayerEnqueue.PLAY: AddCriteriaType.PLAY_NOW,
}

HEOS_HA_REPEAT_TYPE_MAP = {
    RepeatType.OFF: RepeatMode.OFF,
    RepeatType.ON_ALL: RepeatMode.ALL,
    RepeatType.ON_ONE: RepeatMode.ONE,
}
HA_HEOS_REPEAT_TYPE_MAP = {v: k for k, v in HEOS_HA_REPEAT_TYPE_MAP.items()}

HEOS_MEDIA_TYPE_TO_MEDIA_CLASS = {
    HeosMediaType.ALBUM: MediaClass.ALBUM,
    HeosMediaType.ARTIST: MediaClass.ARTIST,
    HeosMediaType.CONTAINER: MediaClass.DIRECTORY,
    HeosMediaType.GENRE: MediaClass.GENRE,
    HeosMediaType.HEOS_SERVER: MediaClass.DIRECTORY,
    HeosMediaType.HEOS_SERVICE: MediaClass.DIRECTORY,
    HeosMediaType.MUSIC_SERVICE: MediaClass.DIRECTORY,
    HeosMediaType.PLAYLIST: MediaClass.PLAYLIST,
    HeosMediaType.SONG: MediaClass.TRACK,
    HeosMediaType.STATION: MediaClass.TRACK,
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add media players for a config entry."""
    services.register_media_player_services()

    def add_entities_callback(players: Sequence[HeosPlayer]) -> None:
        """Add entities for each player."""
        async_add_entities(
            [HeosMediaPlayer(entry.runtime_data, player) for player in players]
        )

    coordinator = entry.runtime_data
    coordinator.async_add_platform_callback(add_entities_callback)
    add_entities_callback(list(coordinator.heos.players.values()))


type _FuncType[**_P, _R] = Callable[_P, Awaitable[_R]]
type _ReturnFuncType[**_P, _R] = Callable[_P, Coroutine[Any, Any, _R]]


def catch_action_error[**_P, _R](
    action: str,
) -> Callable[[_FuncType[_P, _R]], _ReturnFuncType[_P, _R]]:
    """Return decorator that catches errors and raises HomeAssistantError."""

    def decorator(func: _FuncType[_P, _R]) -> _ReturnFuncType[_P, _R]:
        @wraps(func)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            try:
                return await func(*args, **kwargs)
            except (HeosError, ValueError) as ex:
                raise HomeAssistantError(
                    translation_domain=HEOS_DOMAIN,
                    translation_key="action_error",
                    translation_placeholders={"action": action, "error": str(ex)},
                ) from ex

        return wrapper

    return decorator


class HeosMediaPlayer(CoordinatorEntity[HeosCoordinator], MediaPlayerEntity):
    """The HEOS player."""

    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = BASE_SUPPORTED_FEATURES
    _attr_media_image_remotely_accessible = True
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: HeosCoordinator, player: HeosPlayer) -> None:
        """Initialize."""
        self._media_position_updated_at: datetime | None = None
        self._player: HeosPlayer = player
        self._attr_unique_id = str(player.player_id)
        model_parts = player.model.split(maxsplit=1)
        manufacturer = model_parts[0] if len(model_parts) == 2 else "HEOS"
        model = model_parts[1] if len(model_parts) == 2 else player.model
        self._attr_device_info = DeviceInfo(
            identifiers={(HEOS_DOMAIN, str(player.player_id))},
            manufacturer=manufacturer,
            model=model,
            name=player.name,
            serial_number=player.serial,  # Only available for some models
            sw_version=player.version,
        )
        super().__init__(coordinator, context=player.player_id)

    async def _player_update(self, event: str) -> None:
        """Handle player attribute updated."""
        if event == heos_const.EVENT_PLAYER_NOW_PLAYING_PROGRESS:
            self._media_position_updated_at = utcnow()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    @callback
    def _get_group_members(self) -> list[str] | None:
        """Get group member entity IDs for the group."""
        if self._player.group_id is None:
            return None
        if not (group := self.coordinator.heos.groups.get(self._player.group_id)):
            return None
        player_ids = [group.lead_player_id, *group.member_player_ids]
        # Resolve player_ids to entity_ids
        entity_registry = er.async_get(self.hass)
        entity_ids = [
            entity_id
            for member_id in player_ids
            if (
                entity_id := entity_registry.async_get_entity_id(
                    Platform.MEDIA_PLAYER, HEOS_DOMAIN, str(member_id)
                )
            )
        ]
        return entity_ids or None

    @callback
    def _update_attributes(self) -> None:
        """Update core attributes of the media player."""
        self._attr_group_members = self._get_group_members()
        self._attr_source_list = self.coordinator.async_get_source_list()
        self._attr_source = self.coordinator.async_get_current_source(
            self._player.now_playing_media
        )
        self._attr_repeat = HEOS_HA_REPEAT_TYPE_MAP[self._player.repeat]
        controls = self._player.now_playing_media.supported_controls
        current_support = [CONTROL_TO_SUPPORT[control] for control in controls]
        self._attr_supported_features = reduce(
            ior, current_support, BASE_SUPPORTED_FEATURES
        )
        if self.support_next_track and self.support_previous_track:
            self._attr_supported_features |= (
                MediaPlayerEntityFeature.REPEAT_SET
                | MediaPlayerEntityFeature.SHUFFLE_SET
            )

    async def async_added_to_hass(self) -> None:
        """Device added to hass."""
        # Update state when attributes of the player change
        self._update_attributes()
        self.async_on_remove(self._player.add_on_player_event(self._player_update))
        await super().async_added_to_hass()

    @catch_action_error("get queue")
    async def async_get_queue(self) -> ServiceResponse:
        """Get the queue for the current player."""
        queue = await self._player.get_queue()
        return {"queue": [dataclasses.asdict(item) for item in queue]}

    @catch_action_error("clear playlist")
    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        await self._player.clear_queue()

    @catch_action_error("pause")
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._player.pause()

    @catch_action_error("play")
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._player.play()

    @catch_action_error("move to previous track")
    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._player.play_previous()

    @catch_action_error("move to next track")
    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._player.play_next()

    @catch_action_error("stop")
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._player.stop()

    @catch_action_error("set mute")
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self._player.set_mute(mute)

    @catch_action_error("play media")
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if heos_source.is_media_uri(media_id):
            media, data = heos_source.from_media_uri(media_id)
            if not isinstance(media, MediaItem):
                raise ValueError(f"Invalid media id '{media_id}'")
            await self._player.play_media(
                media,
                HA_HEOS_ENQUEUE_MAP[kwargs.get(ATTR_MEDIA_ENQUEUE)],
            )
            return

        if media_source.is_media_source_id(media_id):
            media_type = MediaType.URL
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = play_item.url

        if media_type in {MediaType.URL, MediaType.MUSIC}:
            media_id = async_process_play_media_url(self.hass, media_id)

            await self._player.play_url(media_id)
            return

        if media_type == "quick_select":
            # media_id may be an int or a str
            selects = await self._player.get_quick_selects()
            try:
                index: int | None = int(media_id)
            except ValueError:
                # Try finding index by name
                index = next(
                    (index for index, select in selects.items() if select == media_id),
                    None,
                )
            if index is None:
                raise ValueError(f"Invalid quick select '{media_id}'")
            await self._player.play_quick_select(index)
            return

        if media_type == MediaType.PLAYLIST:
            playlists = await self.coordinator.heos.get_playlists()
            playlist = next((p for p in playlists if p.name == media_id), None)
            if not playlist:
                raise ValueError(f"Invalid playlist '{media_id}'")
            add_queue_option = HA_HEOS_ENQUEUE_MAP[kwargs.get(ATTR_MEDIA_ENQUEUE)]
            await self._player.play_media(playlist, add_queue_option)
            return

        if media_type == "favorite":
            # media_id may be an int or str
            try:
                index = int(media_id)
            except ValueError:
                # Try finding index by name
                index = self.coordinator.async_get_favorite_index(media_id)
            if index is None:
                raise ValueError(f"Invalid favorite '{media_id}'")
            await self._player.play_preset_station(index)
            return

        if media_type == "queue":
            # media_id must be an int
            try:
                queue_id = int(media_id)
            except ValueError:
                raise ValueError(f"Invalid queue id '{media_id}'") from None
            await self._player.play_queue(queue_id)
            return

        raise ValueError(f"Unsupported media type '{media_type}'")

    @catch_action_error("select source")
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        # Favorite
        if (index := self.coordinator.async_get_favorite_index(source)) is not None:
            await self._player.play_preset_station(index)
            return
        # Input source
        for input_source in self.coordinator.inputs:
            if input_source.name == source:
                await self._player.play_media(input_source)
                return

        raise ServiceValidationError(
            translation_domain=HEOS_DOMAIN,
            translation_key="unknown_source",
            translation_placeholders={"source": source},
        )

    @catch_action_error("set repeat")
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self._player.set_play_mode(
            HA_HEOS_REPEAT_TYPE_MAP[repeat], self._player.shuffle
        )

    @catch_action_error("set shuffle")
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        await self._player.set_play_mode(self._player.repeat, shuffle)

    @catch_action_error("set volume level")
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._player.set_volume(int(volume * 100))

    @catch_action_error("set group volume level")
    async def async_set_group_volume_level(self, volume_level: float) -> None:
        """Set group volume level."""
        if self._player.group_id is None:
            raise ServiceValidationError(
                translation_domain=HEOS_DOMAIN,
                translation_key="entity_not_grouped",
                translation_placeholders={"entity_id": self.entity_id},
            )
        await self.coordinator.heos.set_group_volume(
            self._player.group_id, int(volume_level * 100)
        )

    @catch_action_error("group volume down")
    async def async_group_volume_down(self) -> None:
        """Turn group volume down for media player."""
        if self._player.group_id is None:
            raise ServiceValidationError(
                translation_domain=HEOS_DOMAIN,
                translation_key="entity_not_grouped",
                translation_placeholders={"entity_id": self.entity_id},
            )
        await self.coordinator.heos.group_volume_down(self._player.group_id)

    @catch_action_error("group volume up")
    async def async_group_volume_up(self) -> None:
        """Turn group volume up for media player."""
        if self._player.group_id is None:
            raise ServiceValidationError(
                translation_domain=HEOS_DOMAIN,
                translation_key="entity_not_grouped",
                translation_placeholders={"entity_id": self.entity_id},
            )
        await self.coordinator.heos.group_volume_up(self._player.group_id)

    @catch_action_error("join players")
    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        player_ids: list[int] = [self._player.player_id]
        # Resolve entity_ids to player_ids
        entity_registry = er.async_get(self.hass)
        for entity_id in group_members:
            entity_entry = entity_registry.async_get(entity_id)
            if entity_entry is None:
                raise ServiceValidationError(
                    translation_domain=HEOS_DOMAIN,
                    translation_key="entity_not_found",
                    translation_placeholders={"entity_id": entity_id},
                )
            if entity_entry.platform != HEOS_DOMAIN:
                raise ServiceValidationError(
                    translation_domain=HEOS_DOMAIN,
                    translation_key="not_heos_media_player",
                    translation_placeholders={"entity_id": entity_id},
                )
            player_id = int(entity_entry.unique_id)
            if player_id not in player_ids:
                player_ids.append(player_id)
        await self.coordinator.heos.set_group(player_ids)

    @catch_action_error("unjoin player")
    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        for group in self.coordinator.heos.groups.values():
            if group.lead_player_id == self._player.player_id:
                # Player is the group leader, this effectively removes the group.
                await self.coordinator.heos.set_group([self._player.player_id])
                return
            if self._player.player_id in group.member_player_ids:
                # Player is a group member, update the group to exclude it
                new_members = [group.lead_player_id, *group.member_player_ids]
                new_members.remove(self._player.player_id)
                await self.coordinator.heos.set_group(new_members)
                return

    async def async_remove_from_queue(self, queue_ids: list[int]) -> None:
        """Remove items from the queue."""
        await self._player.remove_from_queue(queue_ids)

    @catch_action_error("move queue item")
    async def async_move_queue_item(
        self, queue_ids: list[int], destination_position: int
    ) -> None:
        """Move items in the queue."""
        await self._player.move_queue_item(queue_ids, destination_position)

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self._player.available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Get additional attribute about the state."""
        return {
            "media_album_id": self._player.now_playing_media.album_id,
            "media_queue_id": self._player.now_playing_media.queue_id,
            "media_source_id": self._player.now_playing_media.source_id,
            "media_station": self._player.now_playing_media.station,
            "media_type": self._player.now_playing_media.type,
        }

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self._player.is_muted

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self._player.now_playing_media.album

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self._player.now_playing_media.artist

    @property
    def media_content_id(self) -> str | None:
        """Content ID of current playing media."""
        return self._player.now_playing_media.media_id

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        duration = self._player.now_playing_media.duration
        if isinstance(duration, int):
            return int(duration / 1000)
        return None

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        # Some media doesn't have duration but reports position, return None
        if not self._player.now_playing_media.duration:
            return None
        if isinstance(self._player.now_playing_media.current_position, int):
            return int(self._player.now_playing_media.current_position / 1000)
        return None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid."""
        # Some media doesn't have duration but reports position, return None
        if not self._player.now_playing_media.duration:
            return None
        return self._media_position_updated_at

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        # May be an empty string, if so, return None
        image_url = self._player.now_playing_media.image_url
        return image_url if image_url else None

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._player.now_playing_media.song

    @property
    def shuffle(self) -> bool:
        """Boolean if shuffle is enabled."""
        return self._player.shuffle

    @property
    def state(self) -> MediaPlayerState:
        """State of the player."""
        return PLAY_STATE_TO_STATE[self._player.state]

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return self._player.volume / 100

    async def _async_browse_media_root(self) -> BrowseMedia:
        """Return media browsing root."""
        if not self.coordinator.heos.music_sources:
            try:
                await self.coordinator.heos.get_music_sources()
            except HeosError as error:
                _LOGGER.debug("Unable to load music sources: %s", error)
        children: list[BrowseMedia] = [
            _media_to_browse_media(source)
            for source in self.coordinator.heos.music_sources.values()
            if source.available or source.source_id == heos_const.MUSIC_SOURCE_TUNEIN
        ]
        root = BrowseMedia(
            title="Music Sources",
            media_class=MediaClass.DIRECTORY,
            children_media_class=MediaClass.DIRECTORY,
            media_content_type="",
            media_content_id=BROWSE_ROOT,
            can_expand=True,
            can_play=False,
            children=children,
        )
        # Append media source items
        with suppress(BrowseError):
            browse = await self._async_browse_media_source()
            # If domain is None, it's an overview of available sources
            if browse.domain is None and browse.children:
                children.extend(browse.children)
            else:
                children.append(browse)
        return root

    async def _async_browse_heos_media(self, media_content_id: str) -> BrowseMedia:
        """Browse a HEOS media item."""
        media, data = heos_source.from_media_uri(media_content_id)
        browse_media = _media_to_browse_media(media)
        try:
            browse_result = await self.coordinator.heos.browse_media(media)
        except HeosError as error:
            _LOGGER.debug("Unable to browse media %s: %s", media, error)
        else:
            browse_media.children = [
                _media_to_browse_media(item)
                for item in browse_result.items
                if item.browsable or item.playable
            ]
        return browse_media

    async def _async_browse_media_source(
        self, media_content_id: str | None = None
    ) -> BrowseMediaSource:
        """Browse a media source item."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        if media_content_id in (None, BROWSE_ROOT):
            return await self._async_browse_media_root()
        assert media_content_id is not None
        if heos_source.is_media_uri(media_content_id):
            return await self._async_browse_heos_media(media_content_id)
        if media_source.is_media_source_id(media_content_id):
            return await self._async_browse_media_source(media_content_id)
        raise ServiceValidationError(
            translation_domain=HEOS_DOMAIN,
            translation_key="unsupported_media_content_id",
            translation_placeholders={"media_content_id": media_content_id},
        )


def _media_to_browse_media(media: MediaItem | MediaMusicSource) -> BrowseMedia:
    """Convert a HEOS media item to a browse media item."""
    can_expand = False
    can_play = False

    if isinstance(media, MediaMusicSource):
        can_expand = (
            media.source_id == heos_const.MUSIC_SOURCE_TUNEIN or media.available
        )
    else:
        can_expand = media.browsable
        can_play = media.playable

    return BrowseMedia(
        can_expand=can_expand,
        can_play=can_play,
        media_content_id=heos_source.to_media_uri(media),
        media_content_type="",
        media_class=HEOS_MEDIA_TYPE_TO_MEDIA_CLASS[media.type],
        title=media.name,
        thumbnail=media.image_url,
    )
