"""Denon HEOS Media Player."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from functools import reduce, wraps
from operator import ior
from typing import Any

from pyheos import (
    AddCriteriaType,
    ControlType,
    HeosError,
    HeosPlayer,
    PlayState,
    RepeatType,
    const as heos_const,
)

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    BrowseMedia,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from . import GroupManager, HeosConfigEntry, SourceManager
from .const import DOMAIN as HEOS_DOMAIN, SIGNAL_HEOS_PLAYER_ADDED, SIGNAL_HEOS_UPDATED
from .coordinator import HeosCoordinator

PARALLEL_UPDATES = 0

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


async def async_setup_entry(
    hass: HomeAssistant, entry: HeosConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add media players for a config entry."""
    players = entry.runtime_data.players
    devices = [
        HeosMediaPlayer(
            entry.runtime_data.coordinator,
            player,
            entry.runtime_data.source_manager,
            entry.runtime_data.group_manager,
        )
        for player in players.values()
    ]
    async_add_entities(devices)


type _FuncType[**_P] = Callable[_P, Awaitable[Any]]
type _ReturnFuncType[**_P] = Callable[_P, Coroutine[Any, Any, None]]


def catch_action_error[**_P](
    action: str,
) -> Callable[[_FuncType[_P]], _ReturnFuncType[_P]]:
    """Return decorator that catches errors and raises HomeAssistantError."""

    def decorator(func: _FuncType[_P]) -> _ReturnFuncType[_P]:
        @wraps(func)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> None:
            try:
                await func(*args, **kwargs)
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

    def __init__(
        self,
        coordinator: HeosCoordinator,
        player: HeosPlayer,
        source_manager: SourceManager,
        group_manager: GroupManager,
    ) -> None:
        """Initialize."""
        self._media_position_updated_at = None
        self._player: HeosPlayer = player
        self._source_manager = source_manager
        self._group_manager = group_manager
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
        self._update_attributes()
        super().__init__(coordinator, context=player.player_id)

    async def _player_update(self, event):
        """Handle player attribute updated."""
        if event == heos_const.EVENT_PLAYER_NOW_PLAYING_PROGRESS:
            self._media_position_updated_at = utcnow()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()

    def _update_attributes(self) -> None:
        """Update core attributes of the media player."""
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
        self.async_on_remove(self._player.add_on_player_event(self._player_update))
        # Update state when heos changes
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_HEOS_UPDATED, self._handle_coordinator_update
            )
        )
        # Register this player's entity_id so it can be resolved by the group manager
        self.async_on_remove(
            self._group_manager.register_media_player(
                self._player.player_id, self.entity_id
            )
        )
        async_dispatcher_send(self.hass, SIGNAL_HEOS_PLAYER_ADDED)
        await super().async_added_to_hass()

    @catch_action_error("clear playlist")
    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        await self._player.clear_queue()

    @catch_action_error("join players")
    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        await self._group_manager.async_join_players(
            self._player.player_id, group_members
        )

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
            playlists = await self._player.heos.get_playlists()
            playlist = next((p for p in playlists if p.name == media_id), None)
            if not playlist:
                raise ValueError(f"Invalid playlist '{media_id}'")
            add_queue_option = HA_HEOS_ENQUEUE_MAP.get(kwargs.get(ATTR_MEDIA_ENQUEUE))

            await self._player.add_to_queue(playlist, add_queue_option)
            return

        if media_type == "favorite":
            # media_id may be an int or str
            try:
                index = int(media_id)
            except ValueError:
                # Try finding index by name
                index = next(
                    (
                        index
                        for index, favorite in self._source_manager.favorites.items()
                        if favorite.name == media_id
                    ),
                    None,
                )
            if index is None:
                raise ValueError(f"Invalid favorite '{media_id}'")
            await self._player.play_preset_station(index)
            return

        raise ValueError(f"Unsupported media type '{media_type}'")

    @catch_action_error("select source")
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._source_manager.play_source(source, self._player)

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

    @catch_action_error("unjoin player")
    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        await self._group_manager.async_unjoin_player(self._player.player_id)

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
    def group_members(self) -> list[str]:
        """List of players which are grouped together."""
        return self._group_manager.group_membership.get(self.entity_id, [])

    @property
    def is_volume_muted(self) -> bool:
        """Boolean if volume is currently muted."""
        return self._player.is_muted

    @property
    def media_album_name(self) -> str:
        """Album name of current playing media, music track only."""
        return self._player.now_playing_media.album

    @property
    def media_artist(self) -> str:
        """Artist of current playing media, music track only."""
        return self._player.now_playing_media.artist

    @property
    def media_content_id(self) -> str:
        """Content ID of current playing media."""
        return self._player.now_playing_media.media_id

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        duration = self._player.now_playing_media.duration
        if isinstance(duration, int):
            return duration / 1000
        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        # Some media doesn't have duration but reports position, return None
        if not self._player.now_playing_media.duration:
            return None
        return self._player.now_playing_media.current_position / 1000

    @property
    def media_position_updated_at(self):
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
    def media_title(self) -> str:
        """Title of current playing media."""
        return self._player.now_playing_media.song

    @property
    def shuffle(self) -> bool:
        """Boolean if shuffle is enabled."""
        return self._player.shuffle

    @property
    def source(self) -> str:
        """Name of the current input source."""
        return self._source_manager.get_current_source(self._player.now_playing_media)

    @property
    def source_list(self) -> list[str]:
        """List of available input sources."""
        return self._source_manager.source_list

    @property
    def state(self) -> MediaPlayerState:
        """State of the player."""
        return PLAY_STATE_TO_STATE[self._player.state]

    @property
    def volume_level(self) -> float:
        """Volume level of the media player (0..1)."""
        return self._player.volume / 100

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
