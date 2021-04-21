"""Support to interface with Sonos players."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from contextlib import suppress
import datetime
import functools as ft
import logging
from typing import Any, Callable
import urllib.parse

import async_timeout
from pysonos import alarms
from pysonos.core import (
    MUSIC_SRC_LINE_IN,
    MUSIC_SRC_RADIO,
    MUSIC_SRC_TV,
    PLAY_MODE_BY_MEANING,
    PLAY_MODES,
    SoCo,
)
from pysonos.data_structures import DidlFavorite
from pysonos.events_base import Event as SonosEvent, SubscriptionBase
from pysonos.exceptions import SoCoException, SoCoUPnPException
import pysonos.music_library
import pysonos.snapshot
import voluptuous as vol

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_ENQUEUE,
    MEDIA_TYPE_ALBUM,
    MEDIA_TYPE_ARTIST,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_TRACK,
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.plex.const import PLEX_URI_SCHEME
from homeassistant.components.plex.services import play_on_sonos
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TIME, STATE_IDLE, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.network import is_internal_request
from homeassistant.util.dt import utcnow

from . import SonosData
from .const import (
    DATA_SONOS,
    DOMAIN as SONOS_DOMAIN,
    MEDIA_TYPES_TO_SONOS,
    PLAYABLE_MEDIA_TYPES,
    SCAN_INTERVAL,
    SEEN_EXPIRE_TIME,
    SONOS_DISCOVERY_UPDATE,
    SONOS_GROUP_UPDATE,
    SONOS_PROPERTIES_UPDATE,
    SONOS_SEEN,
    SONOS_UNSEEN,
)
from .entity import SonosEntity
from .media_browser import build_item_response, get_media, library_payload

_LOGGER = logging.getLogger(__name__)

SUPPORT_SONOS = (
    SUPPORT_BROWSE_MEDIA
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PAUSE
    | SUPPORT_PLAY
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_REPEAT_SET
    | SUPPORT_SEEK
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_STOP
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_VOLUME_SET
)

SOURCE_LINEIN = "Line-in"
SOURCE_TV = "TV"

REPEAT_TO_SONOS = {
    REPEAT_MODE_OFF: False,
    REPEAT_MODE_ALL: True,
    REPEAT_MODE_ONE: "ONE",
}

SONOS_TO_REPEAT = {meaning: mode for mode, meaning in REPEAT_TO_SONOS.items()}

ATTR_SONOS_GROUP = "sonos_group"

UPNP_ERRORS_TO_IGNORE = ["701", "711", "712"]

SERVICE_JOIN = "join"
SERVICE_UNJOIN = "unjoin"
SERVICE_SNAPSHOT = "snapshot"
SERVICE_RESTORE = "restore"
SERVICE_SET_TIMER = "set_sleep_timer"
SERVICE_CLEAR_TIMER = "clear_sleep_timer"
SERVICE_UPDATE_ALARM = "update_alarm"
SERVICE_SET_OPTION = "set_option"
SERVICE_PLAY_QUEUE = "play_queue"
SERVICE_REMOVE_FROM_QUEUE = "remove_from_queue"

ATTR_SLEEP_TIME = "sleep_time"
ATTR_ALARM_ID = "alarm_id"
ATTR_VOLUME = "volume"
ATTR_ENABLED = "enabled"
ATTR_INCLUDE_LINKED_ZONES = "include_linked_zones"
ATTR_MASTER = "master"
ATTR_WITH_GROUP = "with_group"
ATTR_NIGHT_SOUND = "night_sound"
ATTR_SPEECH_ENHANCE = "speech_enhance"
ATTR_QUEUE_POSITION = "queue_position"
ATTR_STATUS_LIGHT = "status_light"

UNAVAILABLE_VALUES = {"", "NOT_IMPLEMENTED", None}


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Sonos from a config entry."""
    platform = entity_platform.current_platform.get()

    async def async_create_entities(soco: SoCo) -> None:
        """Handle device discovery and create entities."""
        async_add_entities([SonosMediaPlayerEntity(soco, hass.data[DATA_SONOS])])

    @service.verify_domain_control(hass, SONOS_DOMAIN)
    async def async_service_handle(service_call: ServiceCall) -> None:
        """Handle dispatched services."""
        assert platform is not None
        entities = await platform.async_extract_from_service(service_call)

        if not entities:
            return

        for entity in entities:
            assert isinstance(entity, SonosMediaPlayerEntity)

        if service_call.service == SERVICE_JOIN:
            master = platform.entities.get(service_call.data[ATTR_MASTER])
            if master:
                await SonosMediaPlayerEntity.join_multi(hass, master, entities)  # type: ignore[arg-type]
            else:
                _LOGGER.error(
                    "Invalid master specified for join service: %s",
                    service_call.data[ATTR_MASTER],
                )
        elif service_call.service == SERVICE_UNJOIN:
            await SonosMediaPlayerEntity.unjoin_multi(hass, entities)  # type: ignore[arg-type]
        elif service_call.service == SERVICE_SNAPSHOT:
            await SonosMediaPlayerEntity.snapshot_multi(
                hass, entities, service_call.data[ATTR_WITH_GROUP]  # type: ignore[arg-type]
            )
        elif service_call.service == SERVICE_RESTORE:
            await SonosMediaPlayerEntity.restore_multi(
                hass, entities, service_call.data[ATTR_WITH_GROUP]  # type: ignore[arg-type]
            )

    async_dispatcher_connect(hass, SONOS_DISCOVERY_UPDATE, async_create_entities)

    # create any entities for devices that exist already
    for uid, soco in hass.data[DATA_SONOS].discovered.items():
        if uid not in hass.data[DATA_SONOS].media_player_entities:
            async_add_entities([SonosMediaPlayerEntity(soco, hass.data[DATA_SONOS])])

    hass.services.async_register(
        SONOS_DOMAIN,
        SERVICE_JOIN,
        async_service_handle,
        cv.make_entity_service_schema({vol.Required(ATTR_MASTER): cv.entity_id}),
    )

    hass.services.async_register(
        SONOS_DOMAIN,
        SERVICE_UNJOIN,
        async_service_handle,
        cv.make_entity_service_schema({}),
    )

    join_unjoin_schema = cv.make_entity_service_schema(
        {vol.Optional(ATTR_WITH_GROUP, default=True): cv.boolean}
    )

    hass.services.async_register(
        SONOS_DOMAIN, SERVICE_SNAPSHOT, async_service_handle, join_unjoin_schema
    )

    hass.services.async_register(
        SONOS_DOMAIN, SERVICE_RESTORE, async_service_handle, join_unjoin_schema
    )

    platform.async_register_entity_service(  # type: ignore
        SERVICE_SET_TIMER,
        {
            vol.Required(ATTR_SLEEP_TIME): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=86399)
            )
        },
        "set_sleep_timer",
    )

    platform.async_register_entity_service(SERVICE_CLEAR_TIMER, {}, "clear_sleep_timer")  # type: ignore

    platform.async_register_entity_service(  # type: ignore
        SERVICE_UPDATE_ALARM,
        {
            vol.Required(ATTR_ALARM_ID): cv.positive_int,
            vol.Optional(ATTR_TIME): cv.time,
            vol.Optional(ATTR_VOLUME): cv.small_float,
            vol.Optional(ATTR_ENABLED): cv.boolean,
            vol.Optional(ATTR_INCLUDE_LINKED_ZONES): cv.boolean,
        },
        "set_alarm",
    )

    platform.async_register_entity_service(  # type: ignore
        SERVICE_SET_OPTION,
        {
            vol.Optional(ATTR_NIGHT_SOUND): cv.boolean,
            vol.Optional(ATTR_SPEECH_ENHANCE): cv.boolean,
            vol.Optional(ATTR_STATUS_LIGHT): cv.boolean,
        },
        "set_option",
    )

    platform.async_register_entity_service(  # type: ignore
        SERVICE_PLAY_QUEUE,
        {vol.Optional(ATTR_QUEUE_POSITION): cv.positive_int},
        "play_queue",
    )

    platform.async_register_entity_service(  # type: ignore
        SERVICE_REMOVE_FROM_QUEUE,
        {vol.Optional(ATTR_QUEUE_POSITION): cv.positive_int},
        "remove_from_queue",
    )


def _get_entity_from_soco_uid(
    hass: HomeAssistant, uid: str
) -> SonosMediaPlayerEntity | None:
    """Return SonosMediaPlayerEntity from SoCo uid."""
    return hass.data[DATA_SONOS].media_player_entities.get(uid)  # type: ignore[no-any-return]


def soco_error(errorcodes: list[str] | None = None) -> Callable:
    """Filter out specified UPnP errors from logs and avoid exceptions."""

    def decorator(funct: Callable) -> Callable:
        """Decorate functions."""

        @ft.wraps(funct)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrap for all soco UPnP exception."""
            try:
                return funct(*args, **kwargs)
            except SoCoUPnPException as err:
                if not errorcodes or err.error_code not in errorcodes:
                    _LOGGER.error("Error on %s with %s", funct.__name__, err)
            except SoCoException as err:
                _LOGGER.error("Error on %s with %s", funct.__name__, err)

        return wrapper

    return decorator


def soco_coordinator(funct: Callable) -> Callable:
    """Call function on coordinator."""

    @ft.wraps(funct)
    def wrapper(entity: SonosMediaPlayerEntity, *args: Any, **kwargs: Any) -> Any:
        """Wrap for call to coordinator."""
        if entity.is_coordinator:
            return funct(entity, *args, **kwargs)
        return funct(entity.coordinator, *args, **kwargs)

    return wrapper


def _timespan_secs(timespan: str | None) -> None | float:
    """Parse a time-span into number of seconds."""
    if timespan in UNAVAILABLE_VALUES:
        return None

    assert timespan is not None
    return sum(60 ** x[0] * int(x[1]) for x in enumerate(reversed(timespan.split(":"))))


class SonosMediaPlayerEntity(SonosEntity, MediaPlayerEntity):
    """Representation of a Sonos entity."""

    def __init__(self, player: SoCo, sonos_data: SonosData) -> None:
        """Initialize the Sonos entity."""
        super().__init__(player, sonos_data)
        self._subscriptions: list[SubscriptionBase] = []
        self._poll_timer: Callable | None = None
        self._seen_timer: Callable | None = None
        self._volume_increment = 2
        self._player_volume: int | None = None
        self._player_muted: bool | None = None
        self._play_mode: str | None = None
        self._coordinator: SonosMediaPlayerEntity | None = None
        self._sonos_group: list[SonosMediaPlayerEntity] = [self]
        self._status: str | None = None
        self._uri: str | None = None
        self._media_library = pysonos.music_library.MusicLibrary(self.soco)
        self._media_duration: float | None = None
        self._media_position: float | None = None
        self._media_position_updated_at: datetime.datetime | None = None
        self._media_image_url: str | None = None
        self._media_channel: str | None = None
        self._media_artist: str | None = None
        self._media_album_name: str | None = None
        self._media_title: str | None = None
        self._queue_position: int | None = None
        self._night_sound: bool | None = None
        self._speech_enhance: bool | None = None
        self._source_name: str | None = None
        self._favorites: list[DidlFavorite] = []
        self._soco_snapshot: pysonos.snapshot.Snapshot | None = None
        self._snapshot_group: list[SonosMediaPlayerEntity] | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe sonos events."""
        self.data.media_player_entities[self.unique_id] = self

        await self.async_seen(self.soco)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SONOS_GROUP_UPDATE, self.async_update_groups
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SONOS_SEEN}-{self.unique_id}", self.async_seen
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SONOS_UNSEEN}-{self.unique_id}", self.async_unseen
            )
        )

        if self.hass.is_running:
            async_dispatcher_send(self.hass, SONOS_GROUP_UPDATE)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.soco.uid  # type: ignore[no-any-return]

    def __hash__(self) -> int:
        """Return a hash of self."""
        return hash(self.unique_id)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        speaker_info = self.data.speaker_info[self.unique_id]
        return speaker_info["zone_name"]  # type: ignore[no-any-return]

    @property  # type: ignore[misc]
    @soco_coordinator
    def state(self) -> str:
        """Return the state of the entity."""
        if self._status in (
            "PAUSED_PLAYBACK",
            "STOPPED",
        ):
            # Sonos can consider itself "paused" but without having media loaded
            # (happens if playing Spotify and via Spotify app you pick another device to play on)
            if self.media_title is None:
                return STATE_IDLE
            return STATE_PAUSED
        if self._status in ("PLAYING", "TRANSITIONING"):
            return STATE_PLAYING
        return STATE_IDLE

    @property
    def is_coordinator(self) -> bool:
        """Return true if player is a coordinator."""
        return self._coordinator is None

    @property
    def coordinator(self) -> SoCo:
        """Return coordinator of this player."""
        return self._coordinator

    async def async_seen(self, player: SoCo) -> None:
        """Record that this player was seen right now."""
        was_available = self.available
        _LOGGER.debug("Async seen: %s, was_available: %s", player, was_available)

        self.soco = player

        if self._seen_timer:
            self._seen_timer()

        self._seen_timer = self.hass.helpers.event.async_call_later(
            SEEN_EXPIRE_TIME.total_seconds(), self.async_unseen
        )

        if was_available:
            return

        self._poll_timer = self.hass.helpers.event.async_track_time_interval(
            self.update, SCAN_INTERVAL
        )

        done = await self._async_attach_player()
        if not done:
            assert self._seen_timer is not None
            self._seen_timer()
            await self.async_unseen()

        self.async_write_ha_state()

    async def async_unseen(self) -> None:
        """Make this player unavailable when it was not seen recently."""
        self._seen_timer = None

        if self._poll_timer:
            self._poll_timer()
            self._poll_timer = None

        for subscription in self._subscriptions:
            await subscription.unsubscribe()

        self._subscriptions = []

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._seen_timer is not None

    def _clear_media_position(self) -> None:
        """Clear the media_position."""
        self._media_position = None
        self._media_position_updated_at = None

    def _set_favorites(self) -> None:
        """Set available favorites."""
        self._favorites = []
        for fav in self.soco.music_library.get_sonos_favorites():
            try:
                # Exclude non-playable favorites with no linked resources
                if fav.reference.resources:
                    self._favorites.append(fav)
            except SoCoException as ex:
                # Skip unknown types
                _LOGGER.error("Unhandled favorite '%s': %s", fav.title, ex)

    def _attach_player(self) -> None:
        """Get basic information and add event subscriptions."""
        self._play_mode = self.soco.play_mode
        self.update_volume()
        self._set_favorites()

    async def _async_attach_player(self) -> bool:
        """Get basic information and add event subscriptions."""
        try:
            await self.hass.async_add_executor_job(self._attach_player)

            player = self.soco

            if self._subscriptions:
                raise RuntimeError(
                    f"Attempted to attach subscriptions to player: {player} "
                    f"when existing subscriptions exist: {self._subscriptions}"
                )

            await self._subscribe(player.avTransport, self.async_update_media)
            await self._subscribe(player.renderingControl, self.async_update_volume)
            await self._subscribe(player.zoneGroupTopology, self.async_update_groups)
            await self._subscribe(player.contentDirectory, self.async_update_content)
            await self._subscribe(player.deviceProperties, self.async_update_properties)
            return True
        except SoCoException as ex:
            _LOGGER.warning("Could not connect %s: %s", self.entity_id, ex)
            return False

    async def _subscribe(
        self, target: SubscriptionBase, sub_callback: Callable
    ) -> None:
        """Create a sonos subscription."""
        subscription = await target.subscribe(auto_renew=True)
        subscription.callback = sub_callback
        self._subscriptions.append(subscription)

    def update(self, now: datetime.datetime | None = None) -> None:
        """Retrieve latest state."""
        try:
            self.update_groups()
            self.update_volume()
            if self.is_coordinator:
                self.update_media()
        except SoCoException:
            pass

    @callback
    def async_update_media(self, event: SonosEvent | None = None) -> None:
        """Update information about currently playing media."""
        self.hass.async_add_executor_job(self.update_media, event)

    def update_media(self, event: SonosEvent | None = None) -> None:
        """Update information about currently playing media."""
        variables = event and event.variables

        if variables:
            new_status = variables["transport_state"]
        else:
            transport_info = self.soco.get_current_transport_info()
            new_status = transport_info["current_transport_state"]

        # Ignore transitions, we should get the target state soon
        if new_status == "TRANSITIONING":
            return

        self._play_mode = event.current_play_mode if event else self.soco.play_mode
        self._uri = None
        self._media_duration = None
        self._media_image_url = None
        self._media_channel = None
        self._media_artist = None
        self._media_album_name = None
        self._media_title = None
        self._queue_position = None
        self._source_name = None

        update_position = new_status != self._status
        self._status = new_status

        if variables:
            track_uri = variables["current_track_uri"]
            music_source = self.soco.music_source_from_uri(track_uri)
        else:
            # This causes a network round-trip so we avoid it when possible
            music_source = self.soco.music_source

        if music_source == MUSIC_SRC_TV:
            self.update_media_linein(SOURCE_TV)
        elif music_source == MUSIC_SRC_LINE_IN:
            self.update_media_linein(SOURCE_LINEIN)
        else:
            track_info = self.soco.get_current_track_info()
            if not track_info["uri"]:
                self._clear_media_position()
            else:
                self._uri = track_info["uri"]
                self._media_artist = track_info.get("artist")
                self._media_album_name = track_info.get("album")
                self._media_title = track_info.get("title")

                if music_source == MUSIC_SRC_RADIO:
                    self.update_media_radio(variables)
                else:
                    self.update_media_music(update_position, track_info)

        self.schedule_update_ha_state()

        # Also update slaves
        entities = self.data.media_player_entities.values()
        for entity in entities:
            coordinator = entity.coordinator
            if coordinator and coordinator.unique_id == self.unique_id:
                entity.schedule_update_ha_state()

    def update_media_linein(self, source: str) -> None:
        """Update state when playing from line-in/tv."""
        self._clear_media_position()

        self._media_title = source
        self._source_name = source

    def update_media_radio(self, variables: dict) -> None:
        """Update state when streaming radio."""
        self._clear_media_position()

        try:
            album_art_uri = variables["current_track_meta_data"].album_art_uri
            self._media_image_url = self._media_library.build_album_art_full_uri(
                album_art_uri
            )
        except (TypeError, KeyError, AttributeError):
            pass

        # Non-playing radios will not have a current title. Radios without tagging
        # can have part of the radio URI as title. In these cases we try to use the
        # radio name instead.
        try:
            uri_meta_data = variables["enqueued_transport_uri_meta_data"]
            if isinstance(
                uri_meta_data, pysonos.data_structures.DidlAudioBroadcast
            ) and (
                self.state != STATE_PLAYING
                or self.soco.music_source_from_uri(self._media_title) == MUSIC_SRC_RADIO
                or (
                    isinstance(self._media_title, str)
                    and isinstance(self._uri, str)
                    and self._media_title in self._uri
                )
            ):
                self._media_title = uri_meta_data.title
        except (TypeError, KeyError, AttributeError):
            pass

        media_info = self.soco.get_current_media_info()

        self._media_channel = media_info["channel"]

        # Check if currently playing radio station is in favorites
        for fav in self._favorites:
            if fav.reference.get_uri() == media_info["uri"]:
                self._source_name = fav.title

    def update_media_music(self, update_media_position: bool, track_info: dict) -> None:
        """Update state when playing music tracks."""
        self._media_duration = _timespan_secs(track_info.get("duration"))
        current_position = _timespan_secs(track_info.get("position"))

        # player started reporting position?
        if current_position is not None and self._media_position is None:
            update_media_position = True

        # position jumped?
        if current_position is not None and self._media_position is not None:
            if self.state == STATE_PLAYING:
                assert self._media_position_updated_at is not None
                time_delta = utcnow() - self._media_position_updated_at
                time_diff = time_delta.total_seconds()
            else:
                time_diff = 0

            calculated_position = self._media_position + time_diff

            if abs(calculated_position - current_position) > 1.5:
                update_media_position = True

        if current_position is None:
            self._clear_media_position()
        elif update_media_position:
            self._media_position = current_position
            self._media_position_updated_at = utcnow()

        self._media_image_url = track_info.get("album_art")

        playlist_position = int(track_info.get("playlist_position"))  # type: ignore
        if playlist_position > 0:
            self._queue_position = playlist_position - 1

    @callback
    def async_update_volume(self, event: SonosEvent) -> None:
        """Update information about currently volume settings."""
        variables = event.variables

        if "volume" in variables:
            self._player_volume = int(variables["volume"]["Master"])

        if "mute" in variables:
            self._player_muted = variables["mute"]["Master"] == "1"

        if "night_mode" in variables:
            self._night_sound = variables["night_mode"] == "1"

        if "dialog_level" in variables:
            self._speech_enhance = variables["dialog_level"] == "1"

        self.async_write_ha_state()

    def update_volume(self) -> None:
        """Update information about currently volume settings."""
        self._player_volume = self.soco.volume
        self._player_muted = self.soco.mute
        self._night_sound = self.soco.night_mode
        self._speech_enhance = self.soco.dialog_mode

    def update_groups(self, event: SonosEvent | None = None) -> None:
        """Handle callback for topology change event."""
        coro = self.create_update_groups_coro(event)
        if coro:
            self.hass.add_job(coro)  # type: ignore

    @callback
    def async_update_groups(self, event: SonosEvent | None = None) -> None:
        """Handle callback for topology change event."""
        coro = self.create_update_groups_coro(event)
        if coro:
            self.hass.async_add_job(coro)  # type: ignore

    def create_update_groups_coro(
        self, event: SonosEvent | None = None
    ) -> Coroutine | None:
        """Handle callback for topology change event."""

        def _get_soco_group() -> list[str]:
            """Ask SoCo cache for existing topology."""
            coordinator_uid = self.unique_id
            slave_uids = []

            with suppress(SoCoException):
                if self.soco.group and self.soco.group.coordinator:
                    coordinator_uid = self.soco.group.coordinator.uid
                    slave_uids = [
                        p.uid
                        for p in self.soco.group.members
                        if p.uid != coordinator_uid
                    ]

            return [coordinator_uid] + slave_uids

        async def _async_extract_group(event: SonosEvent) -> list[str]:
            """Extract group layout from a topology event."""
            group = event and event.zone_player_uui_ds_in_group
            if group:
                assert isinstance(group, str)
                return group.split(",")

            return await self.hass.async_add_executor_job(_get_soco_group)

        @callback
        def _async_regroup(group: list[str]) -> None:
            """Rebuild internal group layout."""
            sonos_group = []
            for uid in group:
                entity = _get_entity_from_soco_uid(self.hass, uid)
                if entity:
                    sonos_group.append(entity)

            self._coordinator = None
            self._sonos_group = sonos_group
            self.async_write_ha_state()

            for slave_uid in group[1:]:
                slave = _get_entity_from_soco_uid(self.hass, slave_uid)
                if slave:
                    # pylint: disable=protected-access
                    slave._coordinator = self
                    slave._sonos_group = sonos_group
                    slave.async_schedule_update_ha_state()

        async def _async_handle_group_event(event: SonosEvent) -> None:
            """Get async lock and handle event."""
            if event and self._poll_timer:
                # Cancel poll timer since we do receive events
                self._poll_timer()
                self._poll_timer = None

            async with self.data.topology_condition:
                group = await _async_extract_group(event)

                if self.unique_id == group[0]:
                    _async_regroup(group)

                    self.data.topology_condition.notify_all()

        if event and not hasattr(event, "zone_player_uui_ds_in_group"):
            return None

        return _async_handle_group_event(event)

    @callback
    def async_update_content(self, event: SonosEvent | None = None) -> None:
        """Update information about available content."""
        if event and "favorites_update_id" in event.variables:
            self.hass.async_add_job(self._set_favorites)
            self.async_write_ha_state()

    @callback
    def async_update_properties(self, event: SonosEvent | None = None) -> None:
        """Update information from properties."""
        if not event:
            return
        async_dispatcher_send(
            self.hass, f"{SONOS_PROPERTIES_UPDATE}-{self.unique_id}", event
        )

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self._player_volume and self._player_volume / 100

    @property
    def is_volume_muted(self) -> bool | None:
        """Return true if volume is muted."""
        return self._player_muted

    @property  # type: ignore[misc]
    @soco_coordinator
    def shuffle(self) -> str | None:
        """Shuffling state."""
        shuffle: str = PLAY_MODES[self._play_mode][0]
        return shuffle

    @property  # type: ignore[misc]
    @soco_coordinator
    def repeat(self) -> str | None:
        """Return current repeat mode."""
        sonos_repeat = PLAY_MODES[self._play_mode][1]
        return SONOS_TO_REPEAT[sonos_repeat]

    @property  # type: ignore[misc]
    @soco_coordinator
    def media_content_id(self) -> str | None:
        """Content id of current playing media."""
        return self._uri

    @property
    def media_content_type(self) -> str:
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property  # type: ignore[misc]
    @soco_coordinator
    def media_duration(self) -> float | None:
        """Duration of current playing media in seconds."""
        return self._media_duration

    @property  # type: ignore[misc]
    @soco_coordinator
    def media_position(self) -> float | None:
        """Position of current playing media in seconds."""
        return self._media_position

    @property  # type: ignore[misc]
    @soco_coordinator
    def media_position_updated_at(self) -> datetime.datetime | None:
        """When was the position of the current playing media valid."""
        return self._media_position_updated_at

    @property  # type: ignore[misc]
    @soco_coordinator
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self._media_image_url or None

    @property  # type: ignore[misc]
    @soco_coordinator
    def media_channel(self) -> str | None:
        """Channel currently playing."""
        return self._media_channel or None

    @property  # type: ignore[misc]
    @soco_coordinator
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self._media_artist or None

    @property  # type: ignore[misc]
    @soco_coordinator
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self._media_album_name or None

    @property  # type: ignore[misc]
    @soco_coordinator
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self._media_title or None

    @property  # type: ignore[misc]
    @soco_coordinator
    def queue_position(self) -> int | None:
        """If playing local queue return the position in the queue else None."""
        return self._queue_position

    @property  # type: ignore[misc]
    @soco_coordinator
    def source(self) -> str | None:
        """Name of the current input source."""
        return self._source_name or None

    @property  # type: ignore[misc]
    @soco_coordinator
    def supported_features(self) -> int:
        """Flag media player features that are supported."""
        return SUPPORT_SONOS

    @soco_error()
    def volume_up(self) -> None:
        """Volume up media player."""
        self.soco.volume += self._volume_increment

    @soco_error()
    def volume_down(self) -> None:
        """Volume down media player."""
        self.soco.volume -= self._volume_increment

    @soco_error()
    def set_volume_level(self, volume: str) -> None:
        """Set volume level, range 0..1."""
        self.soco.volume = str(int(volume * 100))

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    @soco_coordinator
    def set_shuffle(self, shuffle: str) -> None:
        """Enable/Disable shuffle mode."""
        sonos_shuffle = shuffle
        sonos_repeat = PLAY_MODES[self._play_mode][1]
        self.soco.play_mode = PLAY_MODE_BY_MEANING[(sonos_shuffle, sonos_repeat)]

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    @soco_coordinator
    def set_repeat(self, repeat: str) -> None:
        """Set repeat mode."""
        sonos_shuffle = PLAY_MODES[self._play_mode][0]
        sonos_repeat = REPEAT_TO_SONOS[repeat]
        self.soco.play_mode = PLAY_MODE_BY_MEANING[(sonos_shuffle, sonos_repeat)]

    @soco_error()
    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        self.soco.mute = mute

    @soco_error()
    @soco_coordinator
    def select_source(self, source: str) -> None:
        """Select input source."""
        if source == SOURCE_LINEIN:
            self.soco.switch_to_line_in()
        elif source == SOURCE_TV:
            self.soco.switch_to_tv()
        else:
            fav = [fav for fav in self._favorites if fav.title == source]
            if len(fav) == 1:
                src = fav.pop()
                uri = src.reference.get_uri()
                if self.soco.music_source_from_uri(uri) in [
                    MUSIC_SRC_RADIO,
                    MUSIC_SRC_LINE_IN,
                ]:
                    self.soco.play_uri(uri, title=source)
                else:
                    self.soco.clear_queue()
                    self.soco.add_to_queue(src.reference)
                    self.soco.play_from_queue(0)

    @property  # type: ignore[misc]
    @soco_coordinator
    def source_list(self) -> list[str]:
        """List of available input sources."""
        sources = [fav.title for fav in self._favorites]

        speaker_info = self.data.speaker_info[self.unique_id]
        model = speaker_info["model_name"].upper()
        if "PLAY:5" in model or "CONNECT" in model:
            sources += [SOURCE_LINEIN]
        elif "PLAYBAR" in model:
            sources += [SOURCE_LINEIN, SOURCE_TV]
        elif "BEAM" in model or "PLAYBASE" in model:
            sources += [SOURCE_TV]

        return sources

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    @soco_coordinator
    def media_play(self) -> None:
        """Send play command."""
        self.soco.play()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    @soco_coordinator
    def media_stop(self) -> None:
        """Send stop command."""
        self.soco.stop()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    @soco_coordinator
    def media_pause(self) -> None:
        """Send pause command."""
        self.soco.pause()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    @soco_coordinator
    def media_next_track(self) -> None:
        """Send next track command."""
        self.soco.next()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    @soco_coordinator
    def media_previous_track(self) -> None:
        """Send next track command."""
        self.soco.previous()

    @soco_error(UPNP_ERRORS_TO_IGNORE)
    @soco_coordinator
    def media_seek(self, position: str) -> None:
        """Send seek command."""
        self.soco.seek(str(datetime.timedelta(seconds=int(position))))

    @soco_error()
    @soco_coordinator
    def clear_playlist(self) -> None:
        """Clear players playlist."""
        self.soco.clear_queue()

    @soco_error()
    @soco_coordinator
    def play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """
        Send the play_media command to the media player.

        If media_id is a Plex payload, attempt Plex->Sonos playback.

        If media_type is "playlist", media_id should be a Sonos
        Playlist name.  Otherwise, media_id should be a URI.

        If ATTR_MEDIA_ENQUEUE is True, add `media_id` to the queue.
        """
        if media_id and media_id.startswith(PLEX_URI_SCHEME):
            media_id = media_id[len(PLEX_URI_SCHEME) :]
            play_on_sonos(self.hass, media_type, media_id, self.name)  # type: ignore[no-untyped-call]
        elif media_type in (MEDIA_TYPE_MUSIC, MEDIA_TYPE_TRACK):
            if kwargs.get(ATTR_MEDIA_ENQUEUE):
                try:
                    if self.soco.is_service_uri(media_id):
                        self.soco.add_service_uri_to_queue(media_id)
                    else:
                        self.soco.add_uri_to_queue(media_id)
                except SoCoUPnPException:
                    _LOGGER.error(
                        'Error parsing media uri "%s", '
                        "please check it's a valid media resource "
                        "supported by Sonos",
                        media_id,
                    )
            else:
                if self.soco.is_service_uri(media_id):
                    self.soco.clear_queue()
                    self.soco.add_service_uri_to_queue(media_id)
                    self.soco.play_from_queue(0)
                else:
                    self.soco.play_uri(media_id)
        elif media_type == MEDIA_TYPE_PLAYLIST:
            if media_id.startswith("S:"):
                item = get_media(self._media_library, media_id, media_type)  # type: ignore[no-untyped-call]
                self.soco.play_uri(item.get_uri())
                return
            try:
                playlists = self.soco.get_sonos_playlists()
                playlist = next(p for p in playlists if p.title == media_id)
                self.soco.clear_queue()
                self.soco.add_to_queue(playlist)
                self.soco.play_from_queue(0)
            except StopIteration:
                _LOGGER.error('Could not find a Sonos playlist named "%s"', media_id)
        elif media_type in PLAYABLE_MEDIA_TYPES:
            item = get_media(self._media_library, media_id, media_type)  # type: ignore[no-untyped-call]

            if not item:
                _LOGGER.error('Could not find "%s" in the library', media_id)
                return

            self.soco.play_uri(item.get_uri())
        else:
            _LOGGER.error('Sonos does not support a media type of "%s"', media_type)

    @soco_error()
    def join(
        self, slaves: list[SonosMediaPlayerEntity]
    ) -> list[SonosMediaPlayerEntity]:
        """Form a group with other players."""
        if self._coordinator:
            self.unjoin()
            group = [self]
        else:
            group = self._sonos_group.copy()

        for slave in slaves:
            if slave.unique_id != self.unique_id:
                slave.soco.join(self.soco)
                # pylint: disable=protected-access
                slave._coordinator = self
                if slave not in group:
                    group.append(slave)

        return group

    @staticmethod
    async def join_multi(
        hass: HomeAssistant,
        master: SonosMediaPlayerEntity,
        entities: list[SonosMediaPlayerEntity],
    ) -> None:
        """Form a group with other players."""
        async with hass.data[DATA_SONOS].topology_condition:
            group: list[SonosMediaPlayerEntity] = await hass.async_add_executor_job(
                master.join, entities
            )
            await SonosMediaPlayerEntity.wait_for_groups(hass, [group])

    @soco_error()
    def unjoin(self) -> None:
        """Unjoin the player from a group."""
        self.soco.unjoin()
        self._coordinator = None

    @staticmethod
    async def unjoin_multi(
        hass: HomeAssistant, entities: list[SonosMediaPlayerEntity]
    ) -> None:
        """Unjoin several players from their group."""

        def _unjoin_all(entities: list[SonosMediaPlayerEntity]) -> None:
            """Sync helper."""
            # Unjoin slaves first to prevent inheritance of queues
            coordinators = [e for e in entities if e.is_coordinator]
            slaves = [e for e in entities if not e.is_coordinator]

            for entity in slaves + coordinators:
                entity.unjoin()

        async with hass.data[DATA_SONOS].topology_condition:
            await hass.async_add_executor_job(_unjoin_all, entities)
            await SonosMediaPlayerEntity.wait_for_groups(hass, [[e] for e in entities])

    @soco_error()
    def snapshot(self, with_group: bool) -> None:
        """Snapshot the state of a player."""
        self._soco_snapshot = pysonos.snapshot.Snapshot(self.soco)
        self._soco_snapshot.snapshot()
        if with_group:
            self._snapshot_group = self._sonos_group.copy()
        else:
            self._snapshot_group = None

    @staticmethod
    async def snapshot_multi(
        hass: HomeAssistant, entities: list[SonosMediaPlayerEntity], with_group: bool
    ) -> None:
        """Snapshot all the entities and optionally their groups."""
        # pylint: disable=protected-access

        def _snapshot_all(entities: list[SonosMediaPlayerEntity]) -> None:
            """Sync helper."""
            for entity in entities:
                entity.snapshot(with_group)

        # Find all affected players
        entities_set = set(entities)
        if with_group:
            for entity in list(entities_set):
                entities_set.update(entity._sonos_group)

        async with hass.data[DATA_SONOS].topology_condition:
            await hass.async_add_executor_job(_snapshot_all, entities_set)

    @soco_error()
    def restore(self) -> None:
        """Restore a snapshotted state to a player."""
        try:
            assert self._soco_snapshot is not None
            self._soco_snapshot.restore()
        except (TypeError, AssertionError, AttributeError, SoCoException) as ex:
            # Can happen if restoring a coordinator onto a current slave
            _LOGGER.warning("Error on restore %s: %s", self.entity_id, ex)

        self._soco_snapshot = None
        self._snapshot_group = None

    @staticmethod
    async def restore_multi(
        hass: HomeAssistant, entities: list[SonosMediaPlayerEntity], with_group: bool
    ) -> None:
        """Restore snapshots for all the entities."""
        # pylint: disable=protected-access

        def _restore_groups(
            entities: list[SonosMediaPlayerEntity], with_group: bool
        ) -> list[list[SonosMediaPlayerEntity]]:
            """Pause all current coordinators and restore groups."""
            for entity in (e for e in entities if e.is_coordinator):
                if entity.state == STATE_PLAYING:
                    entity.media_pause()

            groups = []

            if with_group:
                # Unjoin slaves first to prevent inheritance of queues
                for entity in [e for e in entities if not e.is_coordinator]:
                    if entity._snapshot_group != entity._sonos_group:
                        entity.unjoin()

                # Bring back the original group topology
                for entity in (e for e in entities if e._snapshot_group):
                    assert entity._snapshot_group is not None
                    if entity._snapshot_group[0] == entity:
                        entity.join(entity._snapshot_group)
                        groups.append(entity._snapshot_group.copy())

            return groups

        def _restore_players(entities: list[SonosMediaPlayerEntity]) -> None:
            """Restore state of all players."""
            for entity in (e for e in entities if not e.is_coordinator):
                entity.restore()

            for entity in (e for e in entities if e.is_coordinator):
                entity.restore()

        # Find all affected players
        entities_set = {e for e in entities if e._soco_snapshot}
        if with_group:
            for entity in [e for e in entities_set if e._snapshot_group]:
                assert entity._snapshot_group is not None
                entities_set.update(entity._snapshot_group)

        async with hass.data[DATA_SONOS].topology_condition:
            groups = await hass.async_add_executor_job(
                _restore_groups, entities_set, with_group
            )

            await SonosMediaPlayerEntity.wait_for_groups(hass, groups)

            await hass.async_add_executor_job(_restore_players, entities_set)

    @staticmethod
    async def wait_for_groups(
        hass: HomeAssistant, groups: list[list[SonosMediaPlayerEntity]]
    ) -> None:
        """Wait until all groups are present, or timeout."""
        # pylint: disable=protected-access

        def _test_groups(groups: list[list[SonosMediaPlayerEntity]]) -> bool:
            """Return whether all groups exist now."""
            for group in groups:
                coordinator = group[0]

                # Test that coordinator is coordinating
                current_group = coordinator._sonos_group
                if coordinator != current_group[0]:
                    return False

                # Test that slaves match
                if set(group[1:]) != set(current_group[1:]):
                    return False

            return True

        try:
            with async_timeout.timeout(5):
                while not _test_groups(groups):
                    await hass.data[DATA_SONOS].topology_condition.wait()
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout waiting for target groups %s", groups)

        for entity in hass.data[DATA_SONOS].entities:
            entity.soco._zgs_cache.clear()

    @soco_error()
    @soco_coordinator
    def set_sleep_timer(self, sleep_time: int) -> None:
        """Set the timer on the player."""
        self.soco.set_sleep_timer(sleep_time)

    @soco_error()
    @soco_coordinator
    def clear_sleep_timer(self) -> None:
        """Clear the timer on the player."""
        self.soco.set_sleep_timer(None)

    @soco_error()
    @soco_coordinator
    def set_alarm(
        self,
        alarm_id: int,
        time: datetime.datetime | None = None,
        volume: float | None = None,
        enabled: bool | None = None,
        include_linked_zones: bool | None = None,
    ) -> None:
        """Set the alarm clock on the player."""
        alarm = None
        for one_alarm in alarms.get_alarms(self.soco):
            # pylint: disable=protected-access
            if one_alarm._alarm_id == str(alarm_id):
                alarm = one_alarm
        if alarm is None:
            _LOGGER.warning("Did not find alarm with id %s", alarm_id)
            return
        if time is not None:
            alarm.start_time = time
        if volume is not None:
            alarm.volume = int(volume * 100)
        if enabled is not None:
            alarm.enabled = enabled
        if include_linked_zones is not None:
            alarm.include_linked_zones = include_linked_zones
        alarm.save()

    @soco_error()
    def set_option(
        self,
        night_sound: bool | None = None,
        speech_enhance: bool | None = None,
        status_light: bool | None = None,
    ) -> None:
        """Modify playback options."""
        if night_sound is not None and self._night_sound is not None:
            self.soco.night_mode = night_sound

        if speech_enhance is not None and self._speech_enhance is not None:
            self.soco.dialog_mode = speech_enhance

        if status_light is not None:
            self.soco.status_light = status_light

    @soco_error()
    def play_queue(self, queue_position: int = 0) -> None:
        """Start playing the queue."""
        self.soco.play_from_queue(queue_position)

    @soco_error()
    @soco_coordinator
    def remove_from_queue(self, queue_position: int = 0) -> None:
        """Remove item from the queue."""
        self.soco.remove_from_queue(queue_position)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attributes: dict[str, Any] = {
            ATTR_SONOS_GROUP: [e.entity_id for e in self._sonos_group]
        }

        if self._night_sound is not None:
            attributes[ATTR_NIGHT_SOUND] = self._night_sound

        if self._speech_enhance is not None:
            attributes[ATTR_SPEECH_ENHANCE] = self._speech_enhance

        if self.queue_position is not None:
            attributes[ATTR_QUEUE_POSITION] = self.queue_position

        return attributes

    async def async_get_browse_image(
        self,
        media_content_type: str | None,
        media_content_id: str | None,
        media_image_id: str | None = None,
    ) -> tuple[None | str, None | str]:
        """Fetch media browser image to serve via proxy."""
        if (
            media_content_type in [MEDIA_TYPE_ALBUM, MEDIA_TYPE_ARTIST]
            and media_content_id
        ):
            item = await self.hass.async_add_executor_job(
                get_media,
                self._media_library,
                media_content_id,
                MEDIA_TYPES_TO_SONOS[media_content_type],
            )
            image_url = getattr(item, "album_art_uri", None)
            if image_url:
                result = await self._async_fetch_image(image_url)  # type: ignore[no-untyped-call]
                return result  # type: ignore

        return (None, None)

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> Any:
        """Implement the websocket media browsing helper."""
        is_internal = is_internal_request(self.hass)

        def _get_thumbnail_url(
            media_content_type: str,
            media_content_id: str,
            media_image_id: str | None = None,
        ) -> str | None:
            if is_internal:
                item = get_media(  # type: ignore[no-untyped-call]
                    self._media_library,
                    media_content_id,
                    media_content_type,
                )
                return getattr(item, "album_art_uri", None)  # type: ignore[no-any-return]

            return self.get_browse_image_url(
                media_content_type,
                urllib.parse.quote_plus(media_content_id),
                media_image_id,
            )

        if media_content_type in [None, "library"]:
            return await self.hass.async_add_executor_job(
                library_payload, self._media_library, _get_thumbnail_url
            )

        payload = {
            "search_type": media_content_type,
            "idstring": media_content_id,
        }
        response = await self.hass.async_add_executor_job(
            build_item_response, self._media_library, payload, _get_thumbnail_url
        )
        if response is None:
            raise BrowseError(
                f"Media not found: {media_content_type} / {media_content_id}"
            )
        return response
