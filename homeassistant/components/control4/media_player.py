"""Platform for Control4 Rooms Media Players."""

import base64
from dataclasses import dataclass, field
from datetime import timedelta
import enum
import json
import logging
from typing import Any, override

from propcache.api import cached_property
from pyControl4.error_handling import C4Exception
from pyControl4.room import C4Room

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import Control4CoordinatorEntity
from .const import (
    CONF_DIRECTOR,
    CONF_DIRECTOR_ALL_ITEMS,
    CONF_UI_CONFIGURATION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    Control4ConfigEntry,
)
from .director_utils import (
    director_get_entry_variables,
    update_variables_for_config_entry,
)

_LOGGER = logging.getLogger(__name__)

CONTROL4_POWER_STATE = "POWER_STATE"
CONTROL4_VOLUME_STATE = "CURRENT_VOLUME"
CONTROL4_MUTED_STATE = "IS_MUTED"
CONTROL4_CURRENT_VIDEO_DEVICE = "CURRENT_VIDEO_DEVICE"
CONTROL4_PLAYING = "PLAYING"
CONTROL4_PAUSED = "PAUSED"
CONTROL4_STOPPED = "STOPPED"
CONTROL4_SOURCE_STATE = "State"
CONTROL4_MEDIA_INFO = "CURRENT MEDIA INFO"

CONTROL4_PARENT_ID = "parentId"

VARIABLES_OF_INTEREST = {
    CONTROL4_POWER_STATE,
    CONTROL4_VOLUME_STATE,
    CONTROL4_MUTED_STATE,
    CONTROL4_CURRENT_VIDEO_DEVICE,
    CONTROL4_MEDIA_INFO,
    CONTROL4_PLAYING,
    CONTROL4_PAUSED,
    CONTROL4_STOPPED,
    CONTROL4_SOURCE_STATE,
}

CONTROL4_MEDIA_JOIN_EVENT = "control4_media_join"
CONTROL4_MEDIA_JOIN_EVENT_ENTITIES = "joining_entities"
CONTROL4_MEDIA_JOIN_EVENT_SOURCE_IDX = "source_idx"
CONTROL4_BROWSE_ROOT = f"{DOMAIN}_browse_root"
CONTROL4_BROWSE_MODE = f"{DOMAIN}_browse_mode"


class _SourceType(enum.Enum):
    AUDIO = 1
    VIDEO = 2


@dataclass
class _RoomSource:
    """Class for Room Source."""

    source_type: set[_SourceType]
    idx: int
    name: str
    group_members: set[str] = field(default_factory=set)


async def get_rooms(hass: HomeAssistant, entry: Control4ConfigEntry):
    """Return a list of all Control4 rooms."""
    director_all_items = entry.runtime_data[CONF_DIRECTOR_ALL_ITEMS]
    return [
        item
        for item in director_all_items
        if "typeName" in item and item["typeName"] == "room"
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Control4ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Control4 rooms from a config entry."""
    all_rooms = await get_rooms(hass, entry)
    if not all_rooms:
        return

    entry_data = entry.runtime_data

    async def async_update_data() -> dict[int, dict[str, Any]]:
        """Fetch data from Control4 director."""
        try:
            return await update_variables_for_config_entry(
                hass, entry, VARIABLES_OF_INTEREST
            )
        except C4Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator[dict[int, dict[str, Any]]](
        hass,
        _LOGGER,
        config_entry=entry,
        name="room",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    items_by_id = {
        item["id"]: item for item in entry.runtime_data[CONF_DIRECTOR_ALL_ITEMS]
    }
    item_to_parent_map = {
        k: item["parentId"]
        for k, item in items_by_id.items()
        if "parentId" in item and k > 1
    }

    ui_config = entry_data[CONF_UI_CONFIGURATION]
    sources: dict[int, _RoomSource] = {}

    entity_list = []
    for room in all_rooms:
        room_id = room["id"]
        room_has_valid_experience = False

        room_sources: dict[int, _RoomSource] = {}
        for exp in ui_config["experiences"]:
            if room_id == exp["room_id"]:
                exp_type = exp["type"]
                if exp_type not in ("listen", "watch"):
                    continue
                room_has_valid_experience = True

                dev_type = (
                    _SourceType.AUDIO if exp_type == "listen" else _SourceType.VIDEO
                )
                for source in exp["sources"]["source"]:
                    dev_id = source["id"]
                    name = items_by_id.get(dev_id, {}).get(
                        "name", f"Unknown Device - {dev_id}"
                    )
                    if dev_id in sources:
                        sources[dev_id].source_type.add(dev_type)
                    else:
                        sources[dev_id] = _RoomSource(
                            source_type={dev_type}, idx=dev_id, name=name
                        )
                    room_sources[dev_id] = sources[dev_id]

        if room_has_valid_experience:
            item_attributes = await director_get_entry_variables(hass, entry, room_id)
            try:
                hidden = room["roomHidden"]
                entity_list.append(
                    Control4Room(
                        hass,
                        entry_data,
                        coordinator,
                        room["name"],
                        room_id,
                        item_to_parent_map,
                        room_sources,
                        hidden,
                        item_attributes,
                    )
                )
            except KeyError:
                _LOGGER.exception(
                    "Unknown device properties received from Control4: %s",
                    room,
                )
                continue

    async_add_entities(entity_list, True)


class Control4Room(Control4CoordinatorEntity, MediaPlayerEntity):  # type: ignore[misc]
    """Control4 Room entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: dict,
        coordinator: DataUpdateCoordinator[dict[int, dict[str, Any]]],
        name: str,
        room_id: int,
        id_to_parent: dict[int, int],
        sources: dict[int, _RoomSource],
        room_hidden: bool,
        device_attributes: dict,
    ) -> None:
        """Initialize Control4 room entity."""
        super().__init__(
            entry_data,
            coordinator,
            None,
            room_id,
            device_name=name,
            device_manufacturer=None,
            device_model=None,
            device_id=room_id,
            device_area=None,
            device_attributes=device_attributes,
        )
        self.hass = hass
        self._attr_entity_registry_enabled_default = not room_hidden
        self._id_to_parent = id_to_parent
        self._sources = sources
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.GROUPING
            | MediaPlayerEntityFeature.BROWSE_MEDIA
            | MediaPlayerEntityFeature.PLAY_MEDIA
        )
        self._current_source: _RoomSource | None = None
        self.hass.bus.async_listen(CONTROL4_MEDIA_JOIN_EVENT, self._handle_join)

    async def _handle_join(self, event) -> None:
        joining_entities = event.data.get(CONTROL4_MEDIA_JOIN_EVENT_ENTITIES)
        if self.entity_id in joining_entities:
            source_idx = event.data.get(CONTROL4_MEDIA_JOIN_EVENT_SOURCE_IDX)
            if source_idx in self._sources:
                await self.async_select_source(self._sources[source_idx].name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        updated_source_idx = self._get_current_playing_device_id()
        if (
            self._current_source is not None
            and self._current_source.idx != updated_source_idx
        ):
            self._current_source.group_members.remove(self.entity_id)

        if updated_source_idx in self._sources:
            self._current_source = self._sources[updated_source_idx]
            self._current_source.group_members.add(self.entity_id)
        else:
            self._current_source = None

        self.async_write_ha_state()

    def _create_api_object(self):
        """Create a pyControl4 device object.

        This exists so the director token used is always the latest one, without needing to re-init the entire entity.
        """
        return C4Room(self.entry_data[CONF_DIRECTOR], self._idx)

    def _get_device_from_variable(self, var: str) -> int | None:
        current_device = self.coordinator.data[self._idx][var]
        if current_device == 0:
            return None

        return current_device

    def _get_current_video_device_id(self) -> int | None:
        return self._get_device_from_variable(CONTROL4_CURRENT_VIDEO_DEVICE)

    def _get_current_playing_device_id(self) -> int | None:
        media_info = self._get_media_info()
        if media_info:
            if "medSrcDev" in media_info:
                return media_info["medSrcDev"]
            if "deviceid" in media_info:
                return media_info["deviceid"]
        return 0

    def _get_media_info(self) -> dict | None:
        """Get the Media Info Dictionary if populated."""
        media_info = self.coordinator.data[self._idx][CONTROL4_MEDIA_INFO]
        if "mediainfo" in media_info:
            return media_info["mediainfo"]
        return None

    def _get_current_source_state(self) -> str | None:
        current_source = self._get_current_playing_device_id()
        while current_source:
            current_data = self.coordinator.data.get(current_source, None)
            if current_data:
                if current_data.get(CONTROL4_PLAYING, None):
                    return MediaPlayerState.PLAYING
                if current_data.get(CONTROL4_PAUSED, None):
                    return MediaPlayerState.PAUSED
                if current_data.get(CONTROL4_STOPPED, None):
                    return MediaPlayerState.ON
                state = current_data.get(CONTROL4_SOURCE_STATE, None)
                if isinstance(state, str):
                    normalized_state = state.lower()
                    if normalized_state == "playing":
                        return MediaPlayerState.PLAYING
                    if normalized_state == "paused":
                        return MediaPlayerState.PAUSED
                    if normalized_state == "stopped":
                        return MediaPlayerState.ON
            current_source = self._id_to_parent.get(current_source, None)
        return None

    @cached_property
    def device_class(self) -> MediaPlayerDeviceClass | None:
        """Return the class of this entity."""
        for avail_source in self._sources.values():
            if _SourceType.VIDEO in avail_source.source_type:
                return MediaPlayerDeviceClass.TV
        return MediaPlayerDeviceClass.SPEAKER

    @property
    def state(self):  # type: ignore[override]
        """Return whether this room is on or idle."""

        if source_state := self._get_current_source_state():
            return source_state

        if self.coordinator.data[self._idx][CONTROL4_POWER_STATE]:
            return MediaPlayerState.ON

        return MediaPlayerState.IDLE

    @property
    def source(self):  # type: ignore[override]
        """Get the current source."""
        current_source = self._get_current_playing_device_id()
        if not current_source or current_source not in self._sources:
            return None
        return self._sources[current_source].name

    @property
    def media_title(self) -> str | None:  # type: ignore[override]
        """Get the Media Title."""
        media_info = self._get_media_info()
        if not media_info:
            return None
        if "title" in media_info:
            return media_info["title"]
        current_source = self._get_current_playing_device_id()
        if not current_source or current_source not in self._sources:
            return None
        return self._sources[current_source].name

    @property
    def media_playlist(self) -> str | None:  # type: ignore[override]
        """Return the genre of the current media as a playlist label."""
        media_info = self._get_media_info()
        if not media_info or "genre" not in media_info:
            return None
        return base64.b64decode(media_info["genre"]).decode("ascii")

    @property
    def media_image_url(self) -> str | None:  # type: ignore[override]
        """Return the image URL for the current media."""
        media_info = self._get_media_info()
        if not media_info or "img" not in media_info:
            return None

        url = base64.b64decode(media_info["img"]).decode("ascii")
        base_url_http = self.entry_data[CONF_DIRECTOR].base_url.replace(
            "https://", "http://"
        )  # avoid self-signed cert issue
        return url.replace("controller:/", base_url_http)

    @property
    def media_artist(self) -> str | None:  # type: ignore[override]
        """Return the artist of the current media."""
        media_info = self._get_media_info()
        if not media_info or "artist" not in media_info:
            return None
        return media_info["artist"]

    @property
    def media_album_name(self) -> str | None:  # type: ignore[override]
        """Return the album name of the current media."""
        media_info = self._get_media_info()
        if not media_info or "album" not in media_info:
            return None
        return media_info["album"]

    @property
    def media_channel(self) -> str | None:  # type: ignore[override]
        """Return the channel of the current media."""
        media_info = self._get_media_info()
        if not media_info or "channel" not in media_info:
            return None
        return media_info["channel"]

    @property
    def media_content_type(self):  # type: ignore[override]
        """Get current content type if available."""
        current_source = self._get_current_playing_device_id()
        if not current_source:
            return None
        if current_source == self._get_current_video_device_id():
            return MediaType.VIDEO
        return MediaType.MUSIC

    async def async_media_play_pause(self):
        """If possible, toggle the current play/pause state.

        Not every source supports play/pause.
        Unfortunately MediaPlayer capabilities are not dynamic,
        so we must determine if play/pause is supported here
        """
        if self._get_current_source_state():
            await super().async_media_play_pause()

    @property
    def source_list(self) -> list[str]:  # type: ignore[override]
        """Get the available source."""
        return [x.name for x in self._sources.values()]

    @property
    def volume_level(self):  # type: ignore[override]
        """Get the volume level."""
        return self.coordinator.data[self._idx][CONTROL4_VOLUME_STATE] / 100

    @property
    def is_volume_muted(self):  # type: ignore[override]
        """Check if the volume is muted."""
        return bool(self.coordinator.data[self._idx][CONTROL4_MUTED_STATE])

    @property
    def group_members(self) -> list[str] | None:  # type: ignore[override]
        """Return the group members sharing the current source."""
        current_source = self._get_current_playing_device_id()
        if not current_source or current_source not in self._sources:
            return None
        return list(self._sources[current_source].group_members)

    async def async_select_source(self, source):
        """Select a new source."""
        current_source = self._get_current_playing_device_id()
        if current_source in self._sources:
            self._sources[current_source].group_members.remove(self.entity_id)
        for avail_source in self._sources.values():
            if avail_source.name == source:
                audio_only = _SourceType.VIDEO not in avail_source.source_type
                if audio_only:
                    await self._create_api_object().set_audio_source(avail_source.idx)
                else:
                    await self._create_api_object().set_video_and_audio_source(
                        avail_source.idx
                    )
                avail_source.group_members.add(self.entity_id)
                break

        await self.coordinator.async_request_refresh()

    async def async_join_players(self, group_members):
        """Fire a join event so other rooms can follow this source."""
        current_source = self._get_current_playing_device_id()
        if current_source and current_source in self._sources:
            event_data = {
                CONTROL4_MEDIA_JOIN_EVENT_SOURCE_IDX: self._sources[current_source].idx,
                CONTROL4_MEDIA_JOIN_EVENT_ENTITIES: group_members,
            }
            self.hass.bus.async_fire(CONTROL4_MEDIA_JOIN_EVENT, event_data)

    async def async_unjoin_player(self):
        """Unjoin by turning the room off."""
        await self.async_turn_off()

    async def async_turn_off(self):
        """Turn off the room."""
        await self._create_api_object().set_room_off()
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute):
        """Mute the room."""
        if mute:
            await self._create_api_object().set_mute_on()
        else:
            await self._create_api_object().set_mute_off()
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume):
        """Set room volume, 0-1 scale."""
        await self._create_api_object().set_volume(int(volume * 100))
        await self.coordinator.async_request_refresh()

    async def async_volume_up(self):
        """Increase the volume by 1."""
        await self._create_api_object().set_increment_volume()
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self):
        """Decrease the volume by 1."""
        await self._create_api_object().set_decrement_volume()
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self):
        """Issue a pause command."""
        await self._create_api_object().set_pause()
        await self.coordinator.async_request_refresh()

    async def async_media_play(self):
        """Issue a play command."""
        await self._create_api_object().set_play()
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self):
        """Issue a stop command."""
        await self._create_api_object().set_stop()
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self):
        """Skip to next track."""
        await self._create_api_object().set_next()
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self):
        """Skip to previous track."""
        await self._create_api_object().set_previous()
        await self.coordinator.async_request_refresh()

    async def _browse_mode(self, mode: str) -> BrowseMedia:
        """Build the Listen/Watch folder from the room's known sources."""
        audio_only = mode == "listen"
        source_type_filter = _SourceType.AUDIO if audio_only else _SourceType.VIDEO
        children = []
        for source in self._sources.values():
            if source_type_filter not in source.source_type:
                continue
            play_payload = {"source_id": source.idx, "audio_only": audio_only}
            children.append(
                BrowseMedia(
                    title=source.name,
                    media_class="music" if audio_only else "video",
                    media_content_type=MediaType.MUSIC
                    if audio_only
                    else MediaType.VIDEO,
                    media_content_id=json.dumps(play_payload),
                    can_play=True,
                    can_expand=False,
                )
            )
        title = "Listen" if audio_only else "Watch"
        return BrowseMedia(
            title=title,
            media_class="directory",
            media_content_type=CONTROL4_BROWSE_MODE,
            media_content_id=mode,
            can_play=False,
            can_expand=True,
            children=children,
        )

    @override
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Return the browse root, or drill into a child node."""
        if media_content_type == CONTROL4_BROWSE_MODE and media_content_id:
            return await self._browse_mode(media_content_id)

        children = []
        has_listen = any(
            _SourceType.AUDIO in source.source_type for source in self._sources.values()
        )
        has_watch = any(
            _SourceType.VIDEO in source.source_type for source in self._sources.values()
        )
        if has_listen:
            children.append(
                BrowseMedia(
                    title="Listen",
                    media_class="directory",
                    media_content_type=CONTROL4_BROWSE_MODE,
                    media_content_id="listen",
                    can_play=False,
                    can_expand=True,
                )
            )
        if has_watch:
            children.append(
                BrowseMedia(
                    title="Watch",
                    media_class="directory",
                    media_content_type=CONTROL4_BROWSE_MODE,
                    media_content_id="watch",
                    can_play=False,
                    can_expand=True,
                )
            )
        return BrowseMedia(
            title=self._device_name or self.name or "Control4",
            media_class="directory",
            media_content_type=CONTROL4_BROWSE_ROOT,
            media_content_id="root",
            can_play=False,
            can_expand=True,
            children=children,
        )

    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Select a source chosen from the browse tree."""
        try:
            payload = json.loads(media_id)
        except json.JSONDecodeError, ValueError:
            return
        if not isinstance(payload, dict):
            return
        source_id = payload.get("source_id")
        if not isinstance(source_id, int):
            return
        room = self._create_api_object()
        if payload.get("audio_only", True):
            await room.set_audio_source(source_id)
        else:
            await room.set_video_and_audio_source(source_id)
        await self.coordinator.async_request_refresh()
