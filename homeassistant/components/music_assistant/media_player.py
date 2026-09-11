"""MediaPlayer platform for Music Assistant integration."""

import asyncio
from base64 import b64decode
import binascii
from collections.abc import Mapping
from contextlib import suppress
import os
from typing import TYPE_CHECKING, Any, override

from music_assistant_client.helpers import LinkedUser
from music_assistant_models.auth import AuthProviderType
from music_assistant_models.constants import PLAYER_CONTROL_NONE
from music_assistant_models.enums import (
    DashboardType,
    EventType,
    MediaType,
    PlayerFeature,
    PlayerState as MassPlayerState,
    PlayerType,
    QueueOption,
    RepeatMode as MassRepeatMode,
)
from music_assistant_models.errors import MediaNotFoundError, MusicAssistantError
from music_assistant_models.event import MassEvent
from music_assistant_models.media_items import ItemMapping, MediaItemType
from music_assistant_models.player_queue import PlayerQueue

from homeassistant.components import media_source, tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_EXTRA,
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType as HAMediaType,
    RepeatMode,
    SearchMedia,
    SearchMediaQuery,
    async_process_play_media_url,
)
from homeassistant.const import ATTR_NAME, STATE_OFF, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp

from . import MusicAssistantConfigEntry
from .const import (
    ATTR_ACTIVE,
    ATTR_ACTIVE_QUEUE,
    ATTR_CURRENT_INDEX,
    ATTR_CURRENT_ITEM,
    ATTR_ELAPSED_TIME,
    ATTR_ITEMS,
    ATTR_MASS_PLAYER_TYPE,
    ATTR_NEXT_ITEM,
    ATTR_QUEUE_ID,
    ATTR_RADIO_MODE,
    ATTR_REPEAT_MODE,
    ATTR_SHUFFLE_ENABLED,
    DOMAIN,
    LOGGER,
)
from .entity import MusicAssistantDashboardEntity, MusicAssistantEntity
from .helpers import catch_musicassistant_error, catch_user_not_found
from .media_browser import async_browse_media, async_search_media
from .schemas import QUEUE_DETAILS_SCHEMA, queue_item_dict_from_mass_item

if TYPE_CHECKING:
    from music_assistant_client.client import MusicAssistantClient
    from music_assistant_models.dashboard import DashboardDevice
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
    | MediaPlayerEntityFeature.SEARCH_MEDIA
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

REPEAT_MODE_MAPPING_TO_HA = {
    MassRepeatMode.OFF: RepeatMode.OFF,
    MassRepeatMode.ONE: RepeatMode.ONE,
    MassRepeatMode.ALL: RepeatMode.ALL,
    # UNKNOWN is intentionally not mapped - will return None
}

MASS_ICON_TO_MDI: Mapping[str, str] = {
    "bluetooth": "mdi:bluetooth",
    "car": "mdi:car",
    "cast": "mdi:cast",
    "headphones": "mdi:headphones",
    "laptop": "mdi:laptop",
    "monitor": "mdi:monitor",
    "radio": "mdi:radio",
    "smartphone": "mdi:cellphone",
    "soundbar": "mdi:soundbar",
    "speaker": "mdi:speaker",
    "speakers": "mdi:speaker-multiple",
    "sun": "mdi:white-balance-sunny",
    "tablet": "mdi:tablet",
    "tv": "mdi:television",
    "vinyl": "mdi:record-player",
}


MEDIA_CONTENT_TYPE_DASHBOARD = "dashboard"
NOW_PLAYING_ID_PREFIX = f"{DashboardType.NOW_PLAYING.value}/"
# the DashboardType value doubles as the provider domain for providers/icon
DASHBOARD_ICON_TYPES = frozenset({DashboardType.PARTY, DashboardType.MUSIC_QUIZ})
DASHBOARD_ICON_PROVIDER_DOMAINS = frozenset(
    icon_type.value for icon_type in DASHBOARD_ICON_TYPES
)


def _get_mdi_icon(icon: str) -> str:
    """Return an MDI icon for a Music Assistant icon."""
    if icon.startswith("mdi:"):
        return icon
    if icon.startswith("mdi-"):
        return icon.replace("mdi-", "mdi:", 1)
    return MASS_ICON_TO_MDI.get(icon, "mdi:speaker")


def _get_player_artwork_url(mass: MusicAssistantClient, player: Player) -> str | None:
    """Return the artwork URL for a player's current media, or None."""
    if player.current_media and player.current_media.image_url:
        # prefer player.current_media which reflects the live state
        # (e.g. current track art from radio stream metadata)
        return player.current_media.image_url
    if (
        player.active_source
        and (queue := mass.player_queues.get(player.active_source))
        and queue.current_item
    ):
        # fallback to static media item image from queue
        return mass.get_media_item_image_url(queue.current_item)
    return None


def _decode_data_uri(data_uri: str) -> tuple[bytes | None, str | None]:
    """Decode a `data:<content-type>;base64,<data>` URI.

    Returns (None, None) if the URI is malformed rather than raising.
    """
    if not data_uri.startswith("data:"):
        return None, None
    header, sep, encoded = data_uri.partition(",")
    if not sep or not encoded:
        return None, None
    if not header.endswith(";base64"):
        return None, None
    content_type = header.removeprefix("data:").removesuffix(";base64")
    if not content_type:
        return None, None
    try:
        decoded = b64decode(encoded, validate=True)
    except binascii.Error, ValueError:
        return None, None
    if not decoded:
        return None, None
    return decoded, content_type


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MusicAssistantConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Music Assistant MediaPlayer(s) from Config Entry."""
    mass = entry.runtime_data.mass

    def add_player(player_id: str) -> None:
        """Handle add player."""
        async_add_entities([MusicAssistantPlayer(mass, player_id)])

    # register callback to add players when they are discovered
    entry.runtime_data.platform_handlers.setdefault(Platform.MEDIA_PLAYER, add_player)

    # known_dashboard_ids is scoped to this setup call, so a reload starts
    # fresh and re-adds whatever is in the dashboard cache.
    known_dashboard_ids: set[str] = set()
    entity_registry = er.async_get(hass)

    def add_dashboards() -> None:
        """Add dashboard players for endpoints not yet known to HA.

        An id already seen this run is skipped only while it still has a
        registered entity - if its entity was removed in the meantime (e.g.
        a stale device deleted via the UI), it's treated as new again so a
        later re-registration doesn't leave it without an entity.
        """
        new_entities: list[MusicAssistantDashboardPlayer] = []
        for dashboard in mass.dashboard.dashboards:
            if dashboard.dashboard_id in known_dashboard_ids and (
                entity_registry.async_get_entity_id(
                    Platform.MEDIA_PLAYER,
                    DOMAIN,
                    f"{dashboard.dashboard_id}_dashboard",
                )
            ):
                continue
            known_dashboard_ids.add(dashboard.dashboard_id)
            new_entities.append(
                MusicAssistantDashboardPlayer(mass, dashboard.dashboard_id)
            )
        if new_entities:
            async_add_entities(new_entities)

    def handle_dashboards_updated(event: MassEvent) -> None:
        """Handle the dashboard endpoint cache being refreshed."""
        add_dashboards()

    entry.async_on_unload(
        mass.subscribe(handle_dashboards_updated, EventType.DASHBOARDS_UPDATED)
    )

    add_dashboards()


class MusicAssistantPlayer(MusicAssistantEntity, MediaPlayerEntity):
    """Representation of MediaPlayerEntity from Music Assistant Player."""

    _attr_name = None
    _attr_media_image_remotely_accessible = True
    _attr_media_content_type = HAMediaType.MUSIC
    _attr_translation_key = "media_player"

    def __init__(self, mass: MusicAssistantClient, player_id: str) -> None:
        """Initialize MediaPlayer entity."""
        super().__init__(mass, player_id)
        self._attr_icon = _get_mdi_icon(self.player.icon)
        self._set_supported_features()
        self._attr_device_class = MediaPlayerDeviceClass.SPEAKER
        self._source_list_mapping: dict[str, str] = {}
        self._sound_mode_list_mapping: dict[str, str] = {}

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

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
    @override
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return additional state attributes."""
        return {
            ATTR_MASS_PLAYER_TYPE: self.player.type.value,
            ATTR_ACTIVE_QUEUE: (
                self.active_queue.queue_id if self.active_queue else None
            ),
        }

    @override
    async def async_on_update(self) -> None:
        """Handle player updates."""
        if not self.available:
            return
        player = self.player
        active_queue = self.active_queue
        # update generic attributes
        if player.powered and player.playback_state is not None:
            self._attr_state = MediaPlayerState(player.playback_state.value)
        else:
            self._attr_state = MediaPlayerState(STATE_OFF)
        # active source and source list (translate to HA source names)
        source_mappings: dict[str, str] = {}
        active_source_name: str | None = None
        for source in player.source_list:
            if source.id == player.active_source:
                active_source_name = source.name
            if source.passive:
                # ignore passive sources because HA does not differentiate between
                # active and passive sources
                continue
            source_mappings[source.name] = source.id
        self._attr_source_list = list(source_mappings.keys())
        self._source_list_mapping = source_mappings
        self._attr_source = active_source_name

        # translation_key, sound_mode.id
        sound_mode_mappings: dict[str, str] = {}
        active_sound_mode_translation_key: str | None = None
        for sound_mode in player.sound_mode_list:
            if sound_mode.passive:
                # ignore passive sound_mode because HA does not differentiate between
                # active and passive sound mode
                continue
            translation_key = sound_mode.translation_key
            if player.active_sound_mode == sound_mode.id:
                active_sound_mode_translation_key = translation_key
            sound_mode_mappings[translation_key] = sound_mode.id

        self._attr_sound_mode_list = list(sound_mode_mappings.keys())
        self._sound_mode_list_mapping = sound_mode_mappings
        self._attr_sound_mode = active_sound_mode_translation_key

        group_members: list[str] = []
        if player.group_members:
            group_members = player.group_members
        elif player.synced_to and (parent := self.mass.players.get(player.synced_to)):
            group_members = parent.group_members

        # translate MA group_members to HA group_members as entity id's
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
        if player.type == PlayerType.GROUP:
            volume: int | None = player.group_volume
        else:
            volume = player.volume_level
        self._attr_volume_level = volume / 100 if volume is not None else None
        self._attr_is_volume_muted = player.volume_muted
        self._update_media_attributes(player, active_queue)
        self._update_media_image_url(player)

    @catch_musicassistant_error
    @override
    async def async_media_play(self) -> None:
        """Send play command to device."""
        await self.mass.players.player_command_play(self.player_id)

    @catch_musicassistant_error
    @override
    async def async_media_pause(self) -> None:
        """Send pause command to device."""
        await self.mass.players.player_command_pause(self.player_id)

    @catch_musicassistant_error
    @override
    async def async_media_stop(self) -> None:
        """Send stop command to device."""
        await self.mass.players.player_command_stop(self.player_id)

    @catch_musicassistant_error
    @override
    async def async_media_next_track(self) -> None:
        """Send next track command to device."""
        await self.mass.players.player_command_next_track(self.player_id)

    @catch_musicassistant_error
    @override
    async def async_media_previous_track(self) -> None:
        """Send previous track command to device."""
        await self.mass.players.player_command_previous_track(self.player_id)

    @catch_musicassistant_error
    @override
    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        position = int(position)
        await self.mass.players.player_command_seek(self.player_id, position)

    @catch_musicassistant_error
    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.mass.players.player_command_volume_mute(self.player_id, mute)

    @catch_musicassistant_error
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Send new volume_level to device."""
        volume = int(volume * 100)
        await self.mass.players.player_command_volume_set(self.player_id, volume)

    @catch_musicassistant_error
    @override
    async def async_volume_up(self) -> None:
        """Send new volume_level to device."""
        await self.mass.players.player_command_volume_up(self.player_id)

    @catch_musicassistant_error
    @override
    async def async_volume_down(self) -> None:
        """Send new volume_level to device."""
        await self.mass.players.player_command_volume_down(self.player_id)

    @catch_musicassistant_error
    @override
    async def async_turn_on(self) -> None:
        """Turn on device."""
        await self.mass.players.player_command_power(self.player_id, True)

    @catch_musicassistant_error
    @override
    async def async_turn_off(self) -> None:
        """Turn off device."""
        await self.mass.players.player_command_power(self.player_id, False)

    @catch_musicassistant_error
    @override
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle state."""
        if not self.active_queue:
            return
        await self.mass.player_queues.queue_command_shuffle(
            self.active_queue.queue_id, shuffle
        )

    @catch_musicassistant_error
    @override
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat state."""
        if not self.active_queue:
            return
        await self.mass.player_queues.queue_command_repeat(
            self.active_queue.queue_id, MassRepeatMode(repeat)
        )

    @catch_musicassistant_error
    @override
    async def async_clear_playlist(self) -> None:
        """Clear players playlist."""
        if TYPE_CHECKING:
            assert self.player.active_source is not None
        if queue := self.mass.player_queues.get(self.player.active_source):
            await self.mass.player_queues.queue_command_clear(queue.queue_id)

    @catch_musicassistant_error
    @override
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
                pre_announce_url=kwargs[ATTR_MEDIA_EXTRA].get("pre_announce_url"),
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
    @override
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
    @override
    async def async_unjoin_player(self) -> None:
        """Remove this player from any group."""
        await self.mass.players.player_command_ungroup(self.player_id)

    @catch_musicassistant_error
    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        source_id = self._source_list_mapping.get(source)
        if source_id is None:
            raise ServiceValidationError(
                f"Source '{source}' not found for player {self.name}"
            )
        await self.mass.players.player_command_select_source(self.player_id, source_id)

    @catch_musicassistant_error
    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        sound_mode_id = self._sound_mode_list_mapping.get(sound_mode)
        if sound_mode_id is None:
            raise ServiceValidationError(
                f"Sound mode '{sound_mode}' not found for player {self.name}"
            )
        await self.mass.players.select_sound_mode(self.player_id, sound_mode_id)

    @catch_musicassistant_error
    async def _async_handle_play_media(
        self,
        media_id: list[str],
        artist: str | None = None,
        album: str | None = None,
        enqueue: MediaPlayerEnqueue | QueueOption | None = None,
        radio_mode: bool | None = None,
        media_type: str | None = None,
        username: str | None = None,
    ) -> None:
        """Send the play_media command to the media player."""
        # An explicit username impersonates that Music Assistant user (the server rejects an
        # unknown name). When omitted, default playback to the Home Assistant user that made
        # the call: the server resolves them by provider link, or plays as the default
        # account (required=False) when that Home Assistant user has no linked account.
        user: str | LinkedUser | None = username
        ha_user_id = self._context.user_id if self._context is not None else None
        if username is None and ha_user_id is not None:
            user = LinkedUser(
                provider=AuthProviderType.HOME_ASSISTANT,
                user_id=ha_user_id,
                required=False,
            )

        media_uris: list[str] = []
        item: MediaItemType | ItemMapping | None = None
        # work out (all) uri(s) to play
        with catch_user_not_found(username):
            for media_id_str in media_id:
                assert self.mass.server_info  # for type checking
                # pre schema 33: verify_item_uri does not exist as API method
                # with schema 33: only local files have to be verified
                if self.mass.server_info.schema_version < 33:
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
                            if (
                                isinstance(item, MediaItemType | ItemMapping)
                                and item.uri
                            ):
                                media_uris.append(item.uri)
                            continue
                    # try local accessible filename
                    elif await asyncio.to_thread(os.path.isfile, media_id_str):
                        media_uris.append(media_id_str)
                        continue
                else:
                    media_id_verify_str = media_id_str
                    if media_type and media_id_str.isnumeric():
                        # construct in library uri as replacement for pre 33 isnumeric path
                        media_id_verify_str = (
                            f"library://{MediaType(media_type).value}/{media_id_str}"
                        )
                    if await self.mass.music.verify_item_uri(
                        uri=media_id_verify_str, user=user
                    ):
                        media_uris.append(media_id_verify_str)
                        continue
                    if await asyncio.to_thread(os.path.isfile, media_id_str):
                        media_uris.append(media_id_str)
                        continue
                # last resort: search for media item by name/search
                if item := await self.mass.music.get_item_by_name(
                    name=media_id_str,
                    artist=artist,
                    album=album,
                    media_type=MediaType(media_type) if media_type else None,
                    user=user,
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
                radio_mode=radio_mode or False,
                user=user,
            )

    @catch_musicassistant_error
    async def _async_handle_play_announcement(
        self,
        url: str | None = None,
        message: str | None = None,
        tts_entity_id: str | None = None,
        use_pre_announce: bool | None = None,
        pre_announce_url: str | None = None,
        announce_volume: int | None = None,
    ) -> None:
        """Send the play_announcement command to the media player."""
        if url is None:
            if TYPE_CHECKING:
                assert message is not None
                assert tts_entity_id is not None
            # a gone or unavailable entity would otherwise yield a url that plays nothing
            tts_state = self.hass.states.get(tts_entity_id)
            if tts_state is None or tts_state.state == STATE_UNAVAILABLE:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="tts_entity_not_available",
                    translation_placeholders={"entity_id": tts_entity_id},
                )
            sourced_media = await media_source.async_resolve_media(
                self.hass,
                tts.generate_media_source_id(self.hass, message, engine=tts_entity_id),
                self.entity_id,
            )
            url = async_process_play_media_url(self.hass, sourced_media.url)
        await self.mass.players.play_announcement(
            self.player_id,
            url,
            pre_announce=use_pre_announce,
            pre_announce_url=pre_announce_url,
            volume_level=announce_volume,
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

    @override
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

    @override
    async def async_search_media(self, query: SearchMediaQuery) -> SearchMedia:
        """Search media."""
        return await async_search_media(
            self.mass,
            query,
        )

    def _update_media_image_url(self, player: Player) -> None:
        """Update image URL."""
        image_url = _get_player_artwork_url(self.mass, player)

        # check if the image is provided via music-assistant and therefore
        # not accessible from the outside
        if image_url:
            self._attr_media_image_remotely_accessible = (
                self.mass.server_url not in image_url
            )

        self._attr_media_image_url = image_url

    def _update_media_attributes(
        self, player: Player, queue: PlayerQueue | None
    ) -> None:
        """Update media attributes from the player's current media."""
        # shuffle and repeat are queue concepts and not part of current_media
        if queue is not None:
            self._attr_app_id = DOMAIN
            self._attr_shuffle = queue.shuffle_enabled
            self._attr_repeat = REPEAT_MODE_MAPPING_TO_HA.get(queue.repeat_mode)
        else:
            self._attr_app_id = player.active_source
            self._attr_shuffle = None
            self._attr_repeat = None

        # the server resolves current_media for every playback scenario
        current_media = player.current_media
        self._attr_media_content_id = (
            current_media.uri if current_media is not None else None
        )
        self._attr_media_title = (
            current_media.title if current_media is not None else None
        )
        self._attr_media_artist = (
            current_media.artist if current_media is not None else None
        )
        self._attr_media_album_name = (
            current_media.album if current_media is not None else None
        )
        self._attr_media_album_artist = (
            current_media.album_artist if current_media is not None else None
        )
        self._attr_media_duration = (
            current_media.duration if current_media is not None else None
        )

        # the server pushes a fresh position anchor on jumps (e.g. seeking)
        if current_media is not None and current_media.elapsed_time is not None:
            self._attr_media_position = int(current_media.elapsed_time)
            self._attr_media_position_updated_at = (
                utc_from_timestamp(current_media.elapsed_time_last_updated)
                if current_media.elapsed_time_last_updated is not None
                else None
            )
        else:
            self._attr_media_position = None
            self._attr_media_position_updated_at = None

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
        if PlayerFeature.SELECT_SOURCE in self.player.supported_features:
            supported_features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if PlayerFeature.SELECT_SOUND_MODE in self.player.supported_features:
            supported_features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
        self._attr_supported_features = supported_features


class MusicAssistantDashboardPlayer(MusicAssistantDashboardEntity, MediaPlayerEntity):
    """Representation of a Music Assistant dashboard display device."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.BROWSE_MEDIA
        | MediaPlayerEntityFeature.TURN_OFF
    )

    def __init__(self, mass: MusicAssistantClient, dashboard_id: str) -> None:
        """Initialize MusicAssistantDashboardPlayer."""
        super().__init__(mass, dashboard_id)
        # decoded provider icons per domain; a failed fetch is cached as None
        self._provider_icon_cache: dict[str, tuple[bytes, str] | None] = {}

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self._update_from_session()
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_session_updated, EventType.DASHBOARD_SESSIONS_UPDATED
            )
        )
        # unscoped: the now_playing session's target player changes per session
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_player_or_queue_updated, EventType.PLAYER_UPDATED
            )
        )
        self.async_on_remove(
            self.mass.subscribe(
                self.__on_player_or_queue_updated, EventType.QUEUE_UPDATED
            )
        )

    @catch_musicassistant_error
    @override
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Show a dashboard on this display."""
        if media_type != MEDIA_CONTENT_TYPE_DASHBOARD:
            raise ServiceValidationError(
                "Music Assistant dashboard players only accept media_content_type "
                f"'{MEDIA_CONTENT_TYPE_DASHBOARD}', got '{media_type}'"
            )
        dashboard_type, player_id = self._parse_play_media_id(media_id)
        await self.mass.dashboard.show(self.dashboard_id, dashboard_type, player_id)

    @catch_musicassistant_error
    @override
    async def async_turn_off(self) -> None:
        """Hide the dashboard from this display."""
        await self.mass.dashboard.hide(self.dashboard_id)

    @override
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Browse the dashboards this display can show."""
        # the browse websocket path doesn't filter on availability
        dashboard = self.mass.dashboard.get(self.dashboard_id)
        if dashboard is None:
            raise BrowseError(f"Display '{self.dashboard_id}' is not available")
        if media_content_id in (None, ""):
            return self._build_root_listing(dashboard)
        if media_content_id == DashboardType.NOW_PLAYING.value:
            if DashboardType.NOW_PLAYING not in dashboard.supported_types:
                raise BrowseError(f"Media not found: {media_content_id}")
            return self._build_now_playing_listing()
        raise BrowseError(f"Media not found: {media_content_id}")

    @property
    @override
    def media_image_hash(self) -> str | None:
        """Hash for the active session's icon, invalidated when the session type changes."""
        session = self.mass.dashboard.get_session(self.dashboard_id)
        if session is not None and session.dashboard in DASHBOARD_ICON_TYPES:
            return session.dashboard.value
        # fall back to the base class hash of media_image_url, so its
        # proxy path serves MA-hosted (non-remotely-accessible) artwork
        return super().media_image_hash

    @override
    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        """Fetch the provider icon for an active party/music_quiz session."""
        session = self.mass.dashboard.get_session(self.dashboard_id)
        if session is None or session.dashboard not in DASHBOARD_ICON_TYPES:
            # let the base class fetch/proxy media_image_url itself
            return await super().async_get_media_image()
        return await self._fetch_provider_icon(session.dashboard.value)

    @override
    async def async_get_browse_image(
        self,
        media_content_type: MediaType | str,
        media_content_id: str,
        media_image_id: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        """Fetch a provider icon for a browse tree leaf."""
        if media_content_id not in DASHBOARD_ICON_PROVIDER_DOMAINS:
            return None, None
        return await self._fetch_provider_icon(media_content_id)

    async def __on_session_updated(self, event: MassEvent) -> None:
        """Handle the dashboard's active session changing."""
        self._update_from_session()
        self.async_write_ha_state()

    async def __on_player_or_queue_updated(self, event: MassEvent) -> None:
        """Refresh now_playing session attributes on player/queue updates."""
        session = self.mass.dashboard.get_session(self.dashboard_id)
        if session is None or session.dashboard != DashboardType.NOW_PLAYING:
            return
        player = self.mass.players.get(session.player_id) if session.player_id else None
        if event.event == EventType.PLAYER_UPDATED:
            matches = event.object_id == session.player_id
        else:
            matches = event.object_id in (
                player.active_source if player else None,
                player.active_group if player else None,
                session.player_id,
            )
        if not matches:
            return
        previous_title = self._attr_media_title
        previous_image_url = self._attr_media_image_url
        self._update_from_session()
        if (
            self._attr_media_title != previous_title
            or self._attr_media_image_url != previous_image_url
        ):
            self.async_write_ha_state()

    def _update_from_session(self) -> None:
        """Update state and media attributes from the active session."""
        session = self.mass.dashboard.get_session(self.dashboard_id)
        if session is None:
            self._attr_state = MediaPlayerState.IDLE
            self._attr_media_content_type = None
            self._attr_media_content_id = None
            self._attr_media_title = None
            self._clear_media_image()
            return
        self._attr_state = MediaPlayerState.PLAYING
        self._attr_media_content_type = MEDIA_CONTENT_TYPE_DASHBOARD
        if session.dashboard == DashboardType.PARTY:
            self._attr_media_content_id = DashboardType.PARTY.value
            self._attr_media_title = "Party"
            self._clear_media_image()
        elif session.dashboard == DashboardType.MUSIC_QUIZ:
            self._attr_media_content_id = DashboardType.MUSIC_QUIZ.value
            self._attr_media_title = "Music quiz"
            self._clear_media_image()
        elif session.dashboard == DashboardType.NOW_PLAYING:
            player_id = session.player_id or ""
            self._attr_media_content_id = f"{NOW_PLAYING_ID_PREFIX}{player_id}"
            player = self.mass.players.get(player_id) if player_id else None
            player_label = player.name if player is not None else player_id
            self._attr_media_title = f"Now playing: {player_label}"
            self._update_session_player_image(player)
        else:
            # a dashboard type this client doesn't recognize (UNKNOWN)
            self._attr_media_content_id = session.dashboard.value
            self._attr_media_title = session.dashboard.value
            self._clear_media_image()

    def _valid_content_ids(self, dashboard: DashboardDevice) -> list[str]:
        """List this display's playable content ids, for error messages."""
        ids = [
            supported.value
            for supported in dashboard.supported_types
            if supported not in (DashboardType.UNKNOWN, DashboardType.NOW_PLAYING)
        ]
        if DashboardType.NOW_PLAYING in dashboard.supported_types:
            # not directly playable on its own; it always needs a player segment
            ids.append(f"{NOW_PLAYING_ID_PREFIX}<player_id>")
        return sorted(ids)

    def _parse_play_media_id(
        self, media_content_id: str
    ) -> tuple[DashboardType, str | None]:
        """Validate a play_media content id and split it into a type and player id."""
        dashboard = self.mass.dashboard.get(self.dashboard_id)
        if dashboard is None:
            raise ServiceValidationError(
                f"Display '{self.dashboard_id}' is not available"
            )
        valid_ids = self._valid_content_ids(dashboard)

        if media_content_id == DashboardType.NOW_PLAYING.value:
            raise ServiceValidationError(
                f"'{DashboardType.NOW_PLAYING.value}' requires a player, expected "
                f"{NOW_PLAYING_ID_PREFIX}<player_id>"
            )

        player_id: str | None = None
        if media_content_id.startswith(NOW_PLAYING_ID_PREFIX):
            dashboard_type = DashboardType.NOW_PLAYING
            player_id = media_content_id.removeprefix(NOW_PLAYING_ID_PREFIX)
        else:
            dashboard_type = DashboardType(media_content_id)

        if dashboard_type == DashboardType.UNKNOWN:
            raise ServiceValidationError(
                f"Unknown dashboard '{media_content_id}', expected one of "
                f"{', '.join(valid_ids)}"
            )
        if dashboard_type not in dashboard.supported_types:
            raise ServiceValidationError(
                f"Display '{dashboard.name}' does not support "
                f"'{dashboard_type.value}', expected one of {', '.join(valid_ids)}"
            )
        if dashboard_type == DashboardType.NOW_PLAYING:
            player = self.mass.players.get(player_id) if player_id else None
            if player is None or not player.expose_to_ha:
                raise ServiceValidationError(
                    f"Unknown or unexposed player '{player_id}'"
                )
        return dashboard_type, player_id

    def _clear_media_image(self) -> None:
        """Clear the media image, e.g. for sessions served by async_get_media_image."""
        self._attr_media_image_url = None
        self._attr_media_image_remotely_accessible = False

    def _update_session_player_image(self, player: Player | None) -> None:
        """Update the media image url from the now_playing session's player."""
        image_url = _get_player_artwork_url(self.mass, player) if player else None
        self._attr_media_image_remotely_accessible = bool(
            image_url and self.mass.server_url not in image_url
        )
        self._attr_media_image_url = image_url

    async def _fetch_provider_icon(
        self, provider_domain: str
    ) -> tuple[bytes | None, str | None]:
        """Fetch and decode a provider icon, caching the decoded result per domain."""
        if provider_domain not in self._provider_icon_cache:
            self._provider_icon_cache[
                provider_domain
            ] = await self._request_provider_icon(provider_domain)
        return self._provider_icon_cache[provider_domain] or (None, None)

    async def _request_provider_icon(
        self, provider_domain: str
    ) -> tuple[bytes, str] | None:
        """Fetch and decode a provider icon from the server, logging on failure."""
        try:
            data_uri = await self.mass.send_command(
                "providers/icon", provider=provider_domain
            )
        except MusicAssistantError:
            LOGGER.debug(
                "Failed to fetch provider icon for %s", provider_domain, exc_info=True
            )
            return None
        if data_uri is None:
            LOGGER.debug("No provider icon available for %s", provider_domain)
            return None
        decoded, content_type = _decode_data_uri(data_uri)
        if decoded is None or content_type is None:
            LOGGER.warning("Malformed provider icon data URI for %s", provider_domain)
            return None
        return decoded, content_type

    def _build_root_listing(self, dashboard: DashboardDevice) -> BrowseMedia:
        """Build the root browse listing, filtered to this display's dashboards."""
        children: list[BrowseMedia] = []
        if DashboardType.PARTY in dashboard.supported_types:
            children.append(
                BrowseMedia(
                    media_class=MediaClass.APP,
                    media_content_id=DashboardType.PARTY.value,
                    media_content_type=MEDIA_CONTENT_TYPE_DASHBOARD,
                    title="Party",
                    can_play=True,
                    can_expand=False,
                    thumbnail=self.get_browse_image_url(
                        MEDIA_CONTENT_TYPE_DASHBOARD, DashboardType.PARTY.value
                    ),
                )
            )
        if DashboardType.MUSIC_QUIZ in dashboard.supported_types:
            children.append(
                BrowseMedia(
                    media_class=MediaClass.APP,
                    media_content_id=DashboardType.MUSIC_QUIZ.value,
                    media_content_type=MEDIA_CONTENT_TYPE_DASHBOARD,
                    title="Music quiz",
                    can_play=True,
                    can_expand=False,
                    thumbnail=self.get_browse_image_url(
                        MEDIA_CONTENT_TYPE_DASHBOARD, DashboardType.MUSIC_QUIZ.value
                    ),
                )
            )
        if DashboardType.NOW_PLAYING in dashboard.supported_types:
            children.append(
                BrowseMedia(
                    media_class=MediaClass.DIRECTORY,
                    media_content_id=DashboardType.NOW_PLAYING.value,
                    media_content_type=MEDIA_CONTENT_TYPE_DASHBOARD,
                    title="Now playing",
                    can_play=False,
                    can_expand=True,
                    children_media_class=MediaClass.APP,
                )
            )

        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="",
            media_content_type=MEDIA_CONTENT_TYPE_DASHBOARD,
            title=dashboard.name,
            can_play=False,
            can_expand=True,
            children=children,
        )

    def _build_now_playing_listing(self) -> BrowseMedia:
        """Build the now playing folder, one playable child per exposed player."""
        players = sorted(
            (player for player in self.mass.players if player.expose_to_ha),
            key=lambda player: player.name,
        )
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=DashboardType.NOW_PLAYING.value,
            media_content_type=MEDIA_CONTENT_TYPE_DASHBOARD,
            title="Now playing",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.APP,
            children=[
                BrowseMedia(
                    media_class=MediaClass.APP,
                    media_content_id=f"{NOW_PLAYING_ID_PREFIX}{player.player_id}",
                    media_content_type=MEDIA_CONTENT_TYPE_DASHBOARD,
                    title=player.name,
                    can_play=True,
                    can_expand=False,
                    thumbnail=_get_player_artwork_url(self.mass, player),
                )
                for player in players
            ],
        )
