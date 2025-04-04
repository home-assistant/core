"""MediaPlayer platform for Music Assistant integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Mapping
from contextlib import suppress
import functools
import os
from typing import TYPE_CHECKING, Any, Concatenate

from music_assistant_models.constants import PLAYER_CONTROL_NONE
from music_assistant_models.enums import (
    EventType,
    MediaType,
    PlayerFeature,
    PlayerState as MassPlayerState,
    QueueOption,
    RepeatMode as MassRepeatMode,
)
from music_assistant_models.errors import MediaNotFoundError, MusicAssistantError
from music_assistant_models.event import MassEvent
from music_assistant_models.media_items import ItemMapping, MediaItemType, Track
from music_assistant_models.player_queue import PlayerQueue
import voluptuous as vol

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EXTRA,
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType as HAMediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.const import ATTR_NAME, STATE_OFF
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.util.dt import utc_from_timestamp

from . import MusicAssistantConfigEntry
from .const import (
    ATTR_ACTIVE,
    ATTR_ACTIVE_QUEUE,
    ATTR_ALBUM,
    ATTR_ANNOUNCE_VOLUME,
    ATTR_ARTIST,
    ATTR_AUTO_PLAY,
    ATTR_CURRENT_INDEX,
    ATTR_CURRENT_ITEM,
    ATTR_ELAPSED_TIME,
    ATTR_ITEMS,
    ATTR_MASS_PLAYER_TYPE,
    ATTR_MEDIA_ID,
    ATTR_MEDIA_TYPE,
    ATTR_NEXT_ITEM,
    ATTR_QUEUE_ID,
    ATTR_RADIO_MODE,
    ATTR_REPEAT_MODE,
    ATTR_SHUFFLE_ENABLED,
    ATTR_SOURCE_PLAYER,
    ATTR_URL,
    ATTR_USE_PRE_ANNOUNCE,
    DOMAIN,
)
from .entity import MusicAssistantEntity
from .media_browser import async_browse_media
from .schemas import QUEUE_DETAILS_SCHEMA, queue_item_dict_from_mass_item

if TYPE_CHECKING:
    from music_assistant_client import MusicAssistantClient
    from music_assistant_models.player import Player

SUPPORTED_FEATURES_BASE = (
    MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.MEDIA_ENQUEUE
    | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
    | MediaPlayerEntityFeature.SEEK
    # we always add pause support,
    # regardless if the underlying player actually natively supports pause
    # because the MA behavior is to internally handle pause with stop
    # (and a resume position) and we'd like to keep the UX consistent
    # background info: https://github.com/home-assistant/core/issues/140118
    | MediaPlayerEntityFeature.PAUSE
)

QUEUE_OPTION_MAP = {
    # map from HA enqueue options to MA enqueue options
    # which are the same but just in case
    MediaPlayerEnqueue.ADD: QueueOption.ADD,
    MediaPlayerEnqueue.NEXT: QueueOption.NEXT,
    MediaPlayerEnqueue.PLAY: QueueOption.PLAY,
    MediaPlayerEnqueue.REPLACE: QueueOption.REPLACE,
}

SERVICE_PLAY_MEDIA_ADVANCED = "play_media"
SERVICE_PLAY_ANNOUNCEMENT = "play_announcement"
SERVICE_TRANSFER_QUEUE = "transfer_queue"
SERVICE_GET_QUEUE = "get_queue"


def catch_musicassistant_error[_R, **P](
    func: Callable[Concatenate[MusicAssistantPlayer, P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[MusicAssistantPlayer, P], Coroutine[Any, Any, _R]]:
    """Check and log commands to players."""

    @functools.wraps(func)
    async def wrapper(
        self: MusicAssistantPlayer, *args: P.args, **kwargs: P.kwargs
    ) -> _R:
        """Catch Music Assistant errors and convert to Home Assistant error."""
        try:
            return await func(self, *args, **kwargs)
        except MusicAssistantError as err:
            error_msg = str(err) or err.__class__.__name__
            raise HomeAssistantError(error_msg) from err

    return wrapper


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant MediaPlayer(s) from Config Entry."""
    mass = entry.runtime_data.mass
    added_ids = set()

    async def handle_player_added(event: MassEvent) -> None:
        """Handle Mass Player Added event."""
        if TYPE_CHECKING:
            assert event.object_id is not None
        if event.object_id in added_ids:
            return
        if not player.expose_to_ha:
            return
        added_ids.add(event.object_id)
        async_add_entities([MusicAssistantPlayer(mass, event.object_id)])

    # register listener for new players
    entry.async_on_unload(mass.subscribe(handle_player_added, EventType.PLAYER_ADDED))
    mass_players = []
    # add all current players
    for player in mass.players:
        if not player.expose_to_ha:
            continue
        added_ids.add(player.player_id)
        mass_players.append(MusicAssistantPlayer(mass, player.player_id))

    async_add_entities(mass_players)

    # add platform service for play_media with advanced options
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_PLAY_MEDIA_ADVANCED,
        {
            vol.Required(ATTR_MEDIA_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_MEDIA_TYPE): vol.Coerce(MediaType),
            vol.Optional(ATTR_MEDIA_ENQUEUE): vol.Coerce(QueueOption),
            vol.Optional(ATTR_ARTIST): cv.string,
            vol.Optional(ATTR_ALBUM): cv.string,
            vol.Optional(ATTR_RADIO_MODE): vol.Coerce(bool),
        },
        "_async_handle_play_media",
    )
    platform.async_register_entity_service(
        SERVICE_PLAY_ANNOUNCEMENT,
        {
            vol.Required(ATTR_URL): cv.string,
            vol.Optional(ATTR_USE_PRE_ANNOUNCE): vol.Coerce(bool),
            vol.Optional(ATTR_ANNOUNCE_VOLUME): vol.Coerce(int),
        },
        "_async_handle_play_announcement",
    )
    platform.async_register_entity_service(
        SERVICE_TRANSFER_QUEUE,
        {
            vol.Optional(ATTR_SOURCE_PLAYER): cv.entity_id,
            vol.Optional(ATTR_AUTO_PLAY): vol.Coerce(bool),
        },
        "_async_handle_transfer_queue",
    )
    platform.async_register_entity_service(
        SERVICE_GET_QUEUE,
        schema=None,
        func="_async_handle_get_queue",
        supports_response=SupportsResponse.ONLY,
    )


class MusicAssistantPlayer(MusicAssistantEntity, MediaPlayerEntity):
    """Representation of MediaPlayerEntity from Music Assistant Player."""

    _attr_name = None
    _attr_media_image_remotely_accessible = True
    _attr_media_content_type = HAMediaType.MUSIC

    def __init__(self, mass: MusicAssistantClient, player_id: str) -> None:
        """Initialize MediaPlayer entity."""
        super().__init__(mass, player_id)
        self._attr_icon = self.player.icon.replace("mdi-", "mdi:")
        self._set_supported_features()
        self._attr_device_class = MediaPlayerDeviceClass.SPEAKER
        self._prev_time: float = 0

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        # we subscribe to player queue time update but we only
        # accept a state change on big time jumps (e.g. seeking)
        async def queue_time_updated(event: MassEvent) -> None:
            if event.object_id != self.player.active_source:
                return
            if abs((self._prev_time or 0) - event.data) > 5:
                await self.async_on_update()
                self.async_write_ha_state()
            self._prev_time = event.data

        self.async_on_remove(
            self.mass.subscribe(
                queue_time_updated,
                EventType.QUEUE_TIME_UPDATED,
            )
        )

        # we subscribe to the player config changed event to update
        # the supported features of the player
        async def player_config_changed(event: MassEvent) -> None:
            self._set_supported_features()
            await self.async_on_update()
            self.async_write_ha_state()

        self.async_on_remove(
            self.mass.subscribe(
                player_config_changed, EventType.PLAYER_CONFIG_UPDATED, self.player_id
            )
        )

    @property
    def active_queue(self) -> PlayerQueue | None:
        """Return the active queue for this player (if any)."""
        if not self.player.active_source:
            return None
        return self.mass.player_queues.get(self.player.active_source)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return additional state attributes."""
        return {
            ATTR_MASS_PLAYER_TYPE: self.player.type.value,
            ATTR_ACTIVE_QUEUE: (
                self.active_queue.queue_id if self.active_queue else None
            ),
        }

    async def async_on_update(self) -> None:
        """Handle player updates."""
        if not self.available:
            return
        player = self.player
        active_queue = self.active_queue
        # update generic attributes
        if player.powered and active_queue is not None:
            self._attr_state = MediaPlayerState(active_queue.state.value)
        if player.powered and player.state is not None:
            self._attr_state = MediaPlayerState(player.state.value)
        else:
            self._attr_state = MediaPlayerState(STATE_OFF)

        group_members: list[str] = []
        if player.group_childs:
            group_members = player.group_childs
        elif player.synced_to and (parent := self.mass.players.get(player.synced_to)):
            group_members = parent.group_childs

        # translate MA group_childs to HA group_members as entity id's
        entity_registry = er.async_get(self.hass)
        group_members_entity_ids: list[str] = [
            entity_id
            for child_id in group_members
            if (
                entity_id := entity_registry.async_get_entity_id(
                    self.platform.domain, DOMAIN, child_id
                )
            )
        ]

        self._attr_group_members = group_members_entity_ids
        self._attr_volume_level = (
            player.volume_level / 100 if player.volume_level is not None else None
        )
        self._attr_is_volume_muted = player.volume_muted
        self._update_media_attributes(player, active_queue)
        self._update_media_image_url(player, active_queue)

    @catch_musicassistant_error
    async def async_media_play(self) -> None:
        """Send play command to device."""
        await self.mass.players.player_command_play(self.player_id)

    @catch_musicassistant_error
    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        await self.mass.players.player_command_pause(self.player_id)

    @catch_musicassistant_error
    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        await self.mass.players.player_command_stop(self.player_id)

    @catch_musicassistant_error
    async def async_media_next_track(self) -> None:
        """Send next track command to device."""
        await self.mass.players.player_command_next_track(self.player_id)

    @catch_musicassistant_error
    async def async_media_previous_track(self) -> None:
        """Send previous track command to device."""
        await self.mass.players.player_command_previous_track(self.player_id)

    @catch_musicassistant_error
    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        position = int(position)
        await self.mass.players.player_command_seek(self.player_id, position)

    @catch_musicassistant_error
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.mass.players.player_command_volume_mute(self.player_id, mute)

    @catch_musicassistant_error
    async def async_set_volume_level(self, volume: float) -> None:
        """Send new volume_level to device."""
        volume = int(volume * 100)
        await self.mass.players.player_command_volume_set(self.player_id, volume)

    @catch_musicassistant_error
    async def async_volume_up(self) -> None:
        """Send new volume_level to device."""
        await self.mass.players.player_command_volume_up(self.player_id)

    @catch_musicassistant_error
    async def async_volume_down(self) -> None:
        """Send new volume_level to device."""
        await self.mass.players.player_command_volume_down(self.player_id)

    @catch_musicassistant_error
    async def async_turn_on(self) -> None:
        """Turn on device."""
        await self.mass.players.player_command_power(self.player_id, True)

    @catch_musicassistant_error
    async def async_turn_off(self) -> None:
        """Turn off device."""
        await self.mass.players.player_command_power(self.player_id, False)

    @catch_musicassistant_error
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle state."""
        if not self.active_queue:
            return
        await self.mass.player_queues.queue_command_shuffle(
            self.active_queue.queue_id, shuffle
        )

    @catch_musicassistant_error
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat state."""
        if not self.active_queue:
            return
        await self.mass.player_queues.queue_command_repeat(
            self.active_queue.queue_id, MassRepeatMode(repeat)
        )

    @catch_musicassistant_error
    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        if TYPE_CHECKING:
            assert self.player.active_source is not None
        if queue := self.mass.player_queues.get(self.player.active_source):
            await self.mass.player_queues.queue_command_clear(queue.queue_id)

    @catch_musicassistant_error
    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Send the play_media command to the media player."""
        if media_source.is_media_source_id(media_id):
            # Handle media_source
            sourced_media = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = sourced_media.url
            media_id = async_process_play_media_url(self.hass, media_id)

        if announce:
            await self._async_handle_play_announcement(
                media_id,
                use_pre_announce=kwargs[ATTR_MEDIA_EXTRA].get("use_pre_announce"),
                announce_volume=kwargs[ATTR_MEDIA_EXTRA].get("announce_volume"),
            )
            return

        # forward to our advanced play_media handler
        await self._async_handle_play_media(
            media_id=[media_id],
            enqueue=enqueue,
            media_type=media_type,
            radio_mode=kwargs[ATTR_MEDIA_EXTRA].get(ATTR_RADIO_MODE),
        )

    @catch_musicassistant_error
    async def async_join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        player_ids: list[str] = []
        entity_registry = er.async_get(self.hass)
        for child_entity_id in group_members:
            # resolve HA entity_id to MA player_id
            if not (entity_reg_entry := entity_registry.async_get(child_entity_id)):
                raise HomeAssistantError(f"Entity {child_entity_id} not found")
            # unique id is the MA player_id
            player_ids.append(entity_reg_entry.unique_id)
        await self.mass.players.player_command_group_many(self.player_id, player_ids)

    @catch_musicassistant_error
    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        await self.mass.players.player_command_ungroup(self.player_id)

    @catch_musicassistant_error
    async def _async_handle_play_media(
        self,
        media_id: list[str],
        artist: str | None = None,
        album: str | None = None,
        enqueue: MediaPlayerEnqueue | QueueOption | None = None,
        radio_mode: bool | None = None,
        media_type: str | None = None,
    ) -> None:
        """Send the play_media command to the media player."""
        media_uris: list[str] = []
        item: MediaItemType | ItemMapping | None = None
        # work out (all) uri(s) to play
        for media_id_str in media_id:
            # URL or URI string
            if "://" in media_id_str:
                media_uris.append(media_id_str)
                continue
            # try content id as library id
            if media_type and media_id_str.isnumeric():
                with suppress(MediaNotFoundError):
                    item = await self.mass.music.get_item(
                        MediaType(media_type), media_id_str, "library"
                    )
                    if isinstance(item, MediaItemType | ItemMapping) and item.uri:
                        media_uris.append(item.uri)
                    continue
            # try local accessible filename
            elif await asyncio.to_thread(os.path.isfile, media_id_str):
                media_uris.append(media_id_str)
                continue
            # last resort: search for media item by name/search
            if item := await self.mass.music.get_item_by_name(
                name=media_id_str,
                artist=artist,
                album=album,
                media_type=MediaType(media_type) if media_type else None,
            ):
                if TYPE_CHECKING:
                    assert item.uri is not None
                media_uris.append(item.uri)

        if not media_uris:
            raise HomeAssistantError(
                f"Could not resolve {media_id} to playable media item"
            )

        # determine active queue to send the play request to
        if TYPE_CHECKING:
            assert self.player.active_source is not None
        if queue := self.mass.player_queues.get(self.player.active_source):
            queue_id = queue.queue_id
        else:
            queue_id = self.player_id

        await self.mass.player_queues.play_media(
            queue_id,
            media=media_uris,
            option=self._convert_queueoption_to_media_player_enqueue(enqueue),
            radio_mode=radio_mode if radio_mode else False,
        )

    @catch_musicassistant_error
    async def _async_handle_play_announcement(
        self,
        url: str,
        use_pre_announce: bool | None = None,
        announce_volume: int | None = None,
    ) -> None:
        """Send the play_announcement command to the media player."""
        await self.mass.players.play_announcement(
            self.player_id, url, use_pre_announce, announce_volume
        )

    @catch_musicassistant_error
    async def _async_handle_transfer_queue(
        self, source_player: str | None = None, auto_play: bool | None = None
    ) -> None:
        """Transfer the current queue to another player."""
        if not source_player:
            # no source player given; try to find a playing player(queue)
            for queue in self.mass.player_queues:
                if queue.state == MassPlayerState.PLAYING:
                    source_queue_id = queue.queue_id
                    break
            else:
                raise HomeAssistantError(
                    "Source player not specified and no playing player found."
                )
        else:
            # resolve HA entity_id to MA player_id
            entity_registry = er.async_get(self.hass)
            if (entity := entity_registry.async_get(source_player)) is None:
                raise HomeAssistantError("Source player not available.")
            source_queue_id = entity.unique_id  # unique_id is the MA player_id
        target_queue_id = self.player_id
        await self.mass.player_queues.transfer_queue(
            source_queue_id, target_queue_id, auto_play
        )

    @catch_musicassistant_error
    async def _async_handle_get_queue(self) -> ServiceResponse:
        """Handle get_queue action."""
        if not self.active_queue:
            raise HomeAssistantError("No active queue found")
        active_queue = self.active_queue
        response: ServiceResponse = QUEUE_DETAILS_SCHEMA(
            {
                ATTR_QUEUE_ID: active_queue.queue_id,
                ATTR_ACTIVE: active_queue.active,
                ATTR_NAME: active_queue.display_name,
                ATTR_ITEMS: active_queue.items,
                ATTR_SHUFFLE_ENABLED: active_queue.shuffle_enabled,
                ATTR_REPEAT_MODE: active_queue.repeat_mode.value,
                ATTR_CURRENT_INDEX: active_queue.current_index,
                ATTR_ELAPSED_TIME: active_queue.corrected_elapsed_time,
                ATTR_CURRENT_ITEM: queue_item_dict_from_mass_item(
                    self.mass, active_queue.current_item
                ),
                ATTR_NEXT_ITEM: queue_item_dict_from_mass_item(
                    self.mass, active_queue.next_item
                ),
            }
        )
        return response

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await async_browse_media(
            self.hass,
            self.mass,
            media_content_id,
            media_content_type,
        )

    def _update_media_image_url(
        self, player: Player, queue: PlayerQueue | None
    ) -> None:
        """Update image URL for the active queue item."""
        if queue is None or queue.current_item is None:
            self._attr_media_image_url = None
            return
        if image_url := self.mass.get_media_item_image_url(queue.current_item):
            self._attr_media_image_remotely_accessible = (
                self.mass.server_url not in image_url
            )
            self._attr_media_image_url = image_url
            return
        self._attr_media_image_url = None

    def _update_media_attributes(
        self, player: Player, queue: PlayerQueue | None
    ) -> None:
        """Update media attributes for the active queue item."""
        self._attr_media_artist = None
        self._attr_media_album_artist = None
        self._attr_media_album_name = None
        self._attr_media_title = None
        self._attr_media_content_id = None
        self._attr_media_duration = None
        self._attr_media_position = None
        self._attr_media_position_updated_at = None

        if queue is None and player.current_media:
            # player has some external source active
            self._attr_media_content_id = player.current_media.uri
            self._attr_app_id = player.active_source
            self._attr_media_title = player.current_media.title
            self._attr_media_artist = player.current_media.artist
            self._attr_media_album_name = player.current_media.album
            self._attr_media_duration = player.current_media.duration
            # shuffle and repeat are not (yet) supported for external sources
            self._attr_shuffle = None
            self._attr_repeat = None
            self._attr_media_position = int(player.elapsed_time or 0)
            self._attr_media_position_updated_at = (
                utc_from_timestamp(player.elapsed_time_last_updated)
                if player.elapsed_time_last_updated
                else None
            )
            self._prev_time = player.elapsed_time or 0
            return

        if queue is None:
            # player has no MA queue active
            self._attr_source = player.active_source
            self._attr_app_id = player.active_source
            return

        # player has an MA queue active (either its own queue or some group queue)
        self._attr_app_id = DOMAIN
        self._attr_shuffle = queue.shuffle_enabled
        self._attr_repeat = queue.repeat_mode.value
        if not (cur_item := queue.current_item):
            # queue is empty
            return

        self._attr_media_content_id = queue.current_item.uri
        self._attr_media_duration = queue.current_item.duration
        self._attr_media_position = int(queue.elapsed_time)
        self._attr_media_position_updated_at = utc_from_timestamp(
            queue.elapsed_time_last_updated
        )
        self._prev_time = queue.elapsed_time

        # handle stream title (radio station icy metadata)
        if (stream_details := cur_item.streamdetails) and stream_details.stream_title:
            self._attr_media_album_name = cur_item.name
            if " - " in stream_details.stream_title:
                stream_title_parts = stream_details.stream_title.split(" - ", 1)
                self._attr_media_title = stream_title_parts[1]
                self._attr_media_artist = stream_title_parts[0]
            else:
                self._attr_media_title = stream_details.stream_title
            return

        if not (media_item := cur_item.media_item):
            # queue is not playing a regular media item (edge case?!)
            self._attr_media_title = cur_item.name
            return

        # queue is playing regular media item
        self._attr_media_title = media_item.name
        # for tracks we can extract more info
        if media_item.media_type == MediaType.TRACK:
            if TYPE_CHECKING:
                assert isinstance(media_item, Track)
            self._attr_media_artist = media_item.artist_str
            if media_item.version:
                self._attr_media_title += f" ({media_item.version})"
            if media_item.album:
                self._attr_media_album_name = media_item.album.name
                self._attr_media_album_artist = getattr(
                    media_item.album, "artist_str", None
                )

    def _convert_queueoption_to_media_player_enqueue(
        self, queue_option: MediaPlayerEnqueue | QueueOption | None
    ) -> QueueOption | None:
        """Convert a QueueOption to a MediaPlayerEnqueue."""
        if isinstance(queue_option, MediaPlayerEnqueue):
            queue_option = QUEUE_OPTION_MAP.get(queue_option)
        return queue_option

    def _set_supported_features(self) -> None:
        """Set supported features based on player capabilities."""
        supported_features = SUPPORTED_FEATURES_BASE
        if PlayerFeature.SET_MEMBERS in self.player.supported_features:
            supported_features |= MediaPlayerEntityFeature.GROUPING
        if self.player.mute_control != PLAYER_CONTROL_NONE:
            supported_features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if self.player.volume_control != PLAYER_CONTROL_NONE:
            supported_features |= MediaPlayerEntityFeature.VOLUME_STEP
            supported_features |= MediaPlayerEntityFeature.VOLUME_SET
        if self.player.power_control != PLAYER_CONTROL_NONE:
            supported_features |= MediaPlayerEntityFeature.TURN_ON
            supported_features |= MediaPlayerEntityFeature.TURN_OFF
        self._attr_supported_features = supported_features
