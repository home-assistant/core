"""Base class for common speaker tasks."""
from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import contextlib
import datetime
from functools import partial
import logging
from typing import Any, Callable
import urllib.parse

import async_timeout
from pysonos.core import MUSIC_SRC_LINE_IN, MUSIC_SRC_RADIO, MUSIC_SRC_TV, SoCo
from pysonos.data_structures import DidlAudioBroadcast
from pysonos.events_base import Event as SonosEvent, SubscriptionBase
from pysonos.exceptions import SoCoException
from pysonos.music_library import MusicLibrary
from pysonos.snapshot import Snapshot

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as ent_reg
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
    dispatcher_connect,
    dispatcher_send,
)
from homeassistant.util import dt as dt_util

from .const import (
    BATTERY_SCAN_INTERVAL,
    DATA_SONOS,
    DOMAIN,
    PLATFORMS,
    SCAN_INTERVAL,
    SEEN_EXPIRE_TIME,
    SONOS_CREATE_BATTERY,
    SONOS_CREATE_MEDIA_PLAYER,
    SONOS_ENTITY_CREATED,
    SONOS_ENTITY_UPDATE,
    SONOS_GROUP_UPDATE,
    SONOS_SEEN,
    SONOS_STATE_PLAYING,
    SONOS_STATE_TRANSITIONING,
    SONOS_STATE_UPDATED,
    SOURCE_LINEIN,
    SOURCE_TV,
)
from .favorites import SonosFavorites
from .helpers import soco_error

EVENT_CHARGING = {
    "CHARGING": True,
    "NOT_CHARGING": False,
}
UNAVAILABLE_VALUES = {"", "NOT_IMPLEMENTED", None}


_LOGGER = logging.getLogger(__name__)


def fetch_battery_info_or_none(soco: SoCo) -> dict[str, Any] | None:
    """Fetch battery_info from the given SoCo object.

    Returns None if the device doesn't support battery info
    or if the device is offline.
    """
    with contextlib.suppress(ConnectionError, TimeoutError, SoCoException):
        return soco.get_battery_info()


def _timespan_secs(timespan: str | None) -> None | float:
    """Parse a time-span into number of seconds."""
    if timespan in UNAVAILABLE_VALUES:
        return None

    assert timespan is not None
    return sum(60 ** x[0] * int(x[1]) for x in enumerate(reversed(timespan.split(":"))))


class SonosMedia:
    """Representation of the current Sonos media."""

    def __init__(self, soco: SoCo) -> None:
        """Initialize a SonosMedia."""
        self.library = MusicLibrary(soco)
        self.play_mode: str | None = None
        self.playback_status: str | None = None

        self.album_name: str | None = None
        self.artist: str | None = None
        self.channel: str | None = None
        self.duration: float | None = None
        self.image_url: str | None = None
        self.queue_position: int | None = None
        self.source_name: str | None = None
        self.title: str | None = None
        self.uri: str | None = None

        self.position: float | None = None
        self.position_updated_at: datetime.datetime | None = None

    def clear(self) -> None:
        """Clear basic media info."""
        self.album_name = None
        self.artist = None
        self.channel = None
        self.duration = None
        self.image_url = None
        self.queue_position = None
        self.source_name = None
        self.title = None
        self.uri = None

    def clear_position(self) -> None:
        """Clear the position attributes."""
        self.position = None
        self.position_updated_at = None


class SonosSpeaker:
    """Representation of a Sonos speaker."""

    def __init__(
        self, hass: HomeAssistant, soco: SoCo, speaker_info: dict[str, Any]
    ) -> None:
        """Initialize a SonosSpeaker."""
        self.hass = hass
        self.soco = soco
        self.household_id: str = soco.household_id
        self.media = SonosMedia(soco)

        self._is_ready: bool = False
        self._subscriptions: list[SubscriptionBase] = []
        self._poll_timer: Callable | None = None
        self._seen_timer: Callable | None = None
        self._platforms_ready: set[str] = set()

        self._entity_creation_dispatcher: Callable | None = None
        self._group_dispatcher: Callable | None = None
        self._seen_dispatcher: Callable | None = None

        self.mac_address = speaker_info["mac_address"]
        self.model_name = speaker_info["model_name"]
        self.version = speaker_info["software_version"]
        self.zone_name = speaker_info["zone_name"]

        self.battery_info: dict[str, Any] | None = None
        self._last_battery_event: datetime.datetime | None = None
        self._battery_poll_timer: Callable | None = None

        self.volume: int | None = None
        self.muted: bool | None = None
        self.night_mode: bool | None = None
        self.dialog_mode: bool | None = None

        self.coordinator: SonosSpeaker | None = None
        self.sonos_group: list[SonosSpeaker] = [self]
        self.sonos_group_entities: list[str] = []
        self.soco_snapshot: Snapshot | None = None
        self.snapshot_group: list[SonosSpeaker] | None = None

    def setup(self) -> None:
        """Run initial setup of the speaker."""
        self.set_basic_info()

        self._entity_creation_dispatcher = dispatcher_connect(
            self.hass,
            f"{SONOS_ENTITY_CREATED}-{self.soco.uid}",
            self.async_handle_new_entity,
        )
        self._group_dispatcher = dispatcher_connect(
            self.hass,
            SONOS_GROUP_UPDATE,
            self.async_update_groups,
        )
        self._seen_dispatcher = dispatcher_connect(
            self.hass, f"{SONOS_SEEN}-{self.soco.uid}", self.async_seen
        )

        if battery_info := fetch_battery_info_or_none(self.soco):
            # Battery events can be infrequent, polling is still necessary
            self.battery_info = battery_info
            self._battery_poll_timer = self.hass.helpers.event.track_time_interval(
                self.async_poll_battery, BATTERY_SCAN_INTERVAL
            )
            dispatcher_send(self.hass, SONOS_CREATE_BATTERY, self)
        else:
            self._platforms_ready.update({BINARY_SENSOR_DOMAIN, SENSOR_DOMAIN})

        dispatcher_send(self.hass, SONOS_CREATE_MEDIA_PLAYER, self)

    async def async_handle_new_entity(self, entity_type: str) -> None:
        """Listen to new entities to trigger first subscription."""
        self._platforms_ready.add(entity_type)
        if self._platforms_ready == PLATFORMS:
            await self.async_subscribe()
            self._is_ready = True

    def write_entity_states(self) -> None:
        """Write states for associated SonosEntity instances."""
        dispatcher_send(self.hass, f"{SONOS_STATE_UPDATED}-{self.soco.uid}")

    @callback
    def async_write_entity_states(self) -> None:
        """Write states for associated SonosEntity instances."""
        async_dispatcher_send(self.hass, f"{SONOS_STATE_UPDATED}-{self.soco.uid}")

    def set_basic_info(self) -> None:
        """Set basic information when speaker is reconnected."""
        self.media.play_mode = self.soco.play_mode
        self.update_volume()

    @property
    def available(self) -> bool:
        """Return whether this speaker is available."""
        return self._seen_timer is not None

    async def async_subscribe(self) -> bool:
        """Initiate event subscriptions."""
        _LOGGER.debug("Creating subscriptions for %s", self.zone_name)
        try:
            await self.hass.async_add_executor_job(self.set_basic_info)

            if self._subscriptions:
                raise RuntimeError(
                    f"Attempted to attach subscriptions to player: {self.soco} "
                    f"when existing subscriptions exist: {self._subscriptions}"
                )

            await asyncio.gather(
                self._subscribe(self.soco.avTransport, self.async_update_media),
                self._subscribe(self.soco.renderingControl, self.async_update_volume),
                self._subscribe(self.soco.contentDirectory, self.async_update_content),
                self._subscribe(
                    self.soco.zoneGroupTopology, self.async_dispatch_groups
                ),
                self._subscribe(
                    self.soco.deviceProperties, self.async_dispatch_properties
                ),
            )
            return True
        except SoCoException as ex:
            _LOGGER.warning("Could not connect %s: %s", self.zone_name, ex)
            return False

    async def _subscribe(
        self, target: SubscriptionBase, sub_callback: Callable
    ) -> None:
        """Create a Sonos subscription."""
        subscription = await target.subscribe(auto_renew=True)
        subscription.callback = sub_callback
        self._subscriptions.append(subscription)

    @callback
    def async_dispatch_properties(self, event: SonosEvent | None = None) -> None:
        """Update properties from event."""
        self.hass.async_create_task(self.async_update_device_properties(event))

    @callback
    def async_dispatch_groups(self, event: SonosEvent | None = None) -> None:
        """Update groups from event."""
        if event and self._poll_timer:
            _LOGGER.debug(
                "Received event, cancelling poll timer for %s", self.zone_name
            )
            self._poll_timer()
            self._poll_timer = None

        self.async_update_groups(event)

    async def async_seen(self, soco: SoCo | None = None) -> None:
        """Record that this speaker was seen right now."""
        if soco is not None:
            self.soco = soco

        was_available = self.available
        _LOGGER.debug("Async seen: %s, was_available: %s", self.soco, was_available)

        if self._seen_timer:
            self._seen_timer()

        self._seen_timer = self.hass.helpers.event.async_call_later(
            SEEN_EXPIRE_TIME.total_seconds(), self.async_unseen
        )

        if was_available:
            self.async_write_entity_states()
            return

        self._poll_timer = self.hass.helpers.event.async_track_time_interval(
            partial(
                async_dispatcher_send,
                self.hass,
                f"{SONOS_ENTITY_UPDATE}-{self.soco.uid}",
            ),
            SCAN_INTERVAL,
        )

        if self._is_ready:
            done = await self.async_subscribe()
            if not done:
                assert self._seen_timer is not None
                self._seen_timer()
                await self.async_unseen()

        self.async_write_entity_states()

    async def async_unseen(self, now: datetime.datetime | None = None) -> None:
        """Make this player unavailable when it was not seen recently."""
        self.async_write_entity_states()

        self._seen_timer = None

        if self._poll_timer:
            self._poll_timer()
            self._poll_timer = None

        for subscription in self._subscriptions:
            await subscription.unsubscribe()

        self._subscriptions = []

    async def async_update_device_properties(self, event: SonosEvent = None) -> None:
        """Update device properties using the provided SonosEvent."""
        if event is None:
            return

        if (more_info := event.variables.get("more_info")) is not None:
            battery_dict = dict(x.split(":") for x in more_info.split(","))
            await self.async_update_battery_info(battery_dict)

        self.async_write_entity_states()

    async def async_update_battery_info(self, battery_dict: dict[str, Any]) -> None:
        """Update battery info using the decoded SonosEvent."""
        self._last_battery_event = dt_util.utcnow()

        is_charging = EVENT_CHARGING[battery_dict["BattChg"]]
        if is_charging == self.charging:
            self.battery_info.update({"Level": int(battery_dict["BattPct"])})
        else:
            if battery_info := await self.hass.async_add_executor_job(
                fetch_battery_info_or_none, self.soco
            ):
                self.battery_info = battery_info

    @property
    def is_coordinator(self) -> bool:
        """Return true if player is a coordinator."""
        return self.coordinator is None

    @property
    def power_source(self) -> str:
        """Return the name of the current power source.

        Observed to be either BATTERY or SONOS_CHARGING_RING or USB_POWER.
        """
        return self.battery_info["PowerSource"]

    @property
    def charging(self) -> bool:
        """Return the charging status of the speaker."""
        return self.power_source != "BATTERY"

    async def async_poll_battery(self, now: datetime.datetime | None = None) -> None:
        """Poll the device for the current battery state."""
        if not self.available:
            return

        if (
            self._last_battery_event
            and dt_util.utcnow() - self._last_battery_event < BATTERY_SCAN_INTERVAL
        ):
            return

        if battery_info := await self.hass.async_add_executor_job(
            fetch_battery_info_or_none, self.soco
        ):
            self.battery_info = battery_info
            self.async_write_entity_states()

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
            coordinator_uid = self.soco.uid
            slave_uids = []

            with contextlib.suppress(SoCoException):
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
            entity_registry = ent_reg.async_get(self.hass)
            sonos_group = []
            sonos_group_entities = []

            for uid in group:
                speaker = self.hass.data[DATA_SONOS].discovered.get(uid)
                if speaker:
                    sonos_group.append(speaker)
                    entity_id = entity_registry.async_get_entity_id(
                        MP_DOMAIN, DOMAIN, uid
                    )
                    sonos_group_entities.append(entity_id)

            self.coordinator = None
            self.sonos_group = sonos_group
            self.sonos_group_entities = sonos_group_entities
            self.async_write_entity_states()

            for slave_uid in group[1:]:
                slave = self.hass.data[DATA_SONOS].discovered.get(slave_uid)
                if slave:
                    slave.coordinator = self
                    slave.sonos_group = sonos_group
                    slave.sonos_group_entities = sonos_group_entities
                    slave.async_write_entity_states()

        async def _async_handle_group_event(event: SonosEvent) -> None:
            """Get async lock and handle event."""

            async with self.hass.data[DATA_SONOS].topology_condition:
                group = await _async_extract_group(event)

                if self.soco.uid == group[0]:
                    _async_regroup(group)

                    self.hass.data[DATA_SONOS].topology_condition.notify_all()

        if event and not hasattr(event, "zone_player_uui_ds_in_group"):
            return None

        return _async_handle_group_event(event)

    @soco_error()
    def join(self, slaves: list[SonosSpeaker]) -> list[SonosSpeaker]:
        """Form a group with other players."""
        if self.coordinator:
            self.unjoin()
            group = [self]
        else:
            group = self.sonos_group.copy()

        for slave in slaves:
            if slave.soco.uid != self.soco.uid:
                slave.soco.join(self.soco)
                slave.coordinator = self
                if slave not in group:
                    group.append(slave)

        return group

    @staticmethod
    async def join_multi(
        hass: HomeAssistant,
        master: SonosSpeaker,
        speakers: list[SonosSpeaker],
    ) -> None:
        """Form a group with other players."""
        async with hass.data[DATA_SONOS].topology_condition:
            group: list[SonosSpeaker] = await hass.async_add_executor_job(
                master.join, speakers
            )
            await SonosSpeaker.wait_for_groups(hass, [group])

    @soco_error()
    def unjoin(self) -> None:
        """Unjoin the player from a group."""
        self.soco.unjoin()
        self.coordinator = None

    @staticmethod
    async def unjoin_multi(hass: HomeAssistant, speakers: list[SonosSpeaker]) -> None:
        """Unjoin several players from their group."""

        def _unjoin_all(speakers: list[SonosSpeaker]) -> None:
            """Sync helper."""
            # Unjoin slaves first to prevent inheritance of queues
            coordinators = [s for s in speakers if s.is_coordinator]
            slaves = [s for s in speakers if not s.is_coordinator]

            for speaker in slaves + coordinators:
                speaker.unjoin()

        async with hass.data[DATA_SONOS].topology_condition:
            await hass.async_add_executor_job(_unjoin_all, speakers)
            await SonosSpeaker.wait_for_groups(hass, [[s] for s in speakers])

    @soco_error()
    def snapshot(self, with_group: bool) -> None:
        """Snapshot the state of a player."""
        self.soco_snapshot = Snapshot(self.soco)
        self.soco_snapshot.snapshot()
        if with_group:
            self.snapshot_group = self.sonos_group.copy()
        else:
            self.snapshot_group = None

    @staticmethod
    async def snapshot_multi(
        hass: HomeAssistant, speakers: list[SonosSpeaker], with_group: bool
    ) -> None:
        """Snapshot all the speakers and optionally their groups."""

        def _snapshot_all(speakers: list[SonosSpeaker]) -> None:
            """Sync helper."""
            for speaker in speakers:
                speaker.snapshot(with_group)

        # Find all affected players
        speakers_set = set(speakers)
        if with_group:
            for speaker in list(speakers_set):
                speakers_set.update(speaker.sonos_group)

        async with hass.data[DATA_SONOS].topology_condition:
            await hass.async_add_executor_job(_snapshot_all, speakers_set)

    @soco_error()
    def restore(self) -> None:
        """Restore a snapshotted state to a player."""
        try:
            assert self.soco_snapshot is not None
            self.soco_snapshot.restore()
        except (TypeError, AssertionError, AttributeError, SoCoException) as ex:
            # Can happen if restoring a coordinator onto a current slave
            _LOGGER.warning("Error on restore %s: %s", self.zone_name, ex)

        self.soco_snapshot = None
        self.snapshot_group = None

    @staticmethod
    async def restore_multi(
        hass: HomeAssistant, speakers: list[SonosSpeaker], with_group: bool
    ) -> None:
        """Restore snapshots for all the speakers."""

        def _restore_groups(
            speakers: list[SonosSpeaker], with_group: bool
        ) -> list[list[SonosSpeaker]]:
            """Pause all current coordinators and restore groups."""
            for speaker in (s for s in speakers if s.is_coordinator):
                if speaker.media.playback_status == SONOS_STATE_PLAYING:
                    hass.async_create_task(speaker.soco.pause())

            groups = []

            if with_group:
                # Unjoin slaves first to prevent inheritance of queues
                for speaker in [s for s in speakers if not s.is_coordinator]:
                    if speaker.snapshot_group != speaker.sonos_group:
                        speaker.unjoin()

                # Bring back the original group topology
                for speaker in (s for s in speakers if s.snapshot_group):
                    assert speaker.snapshot_group is not None
                    if speaker.snapshot_group[0] == speaker:
                        speaker.join(speaker.snapshot_group)
                        groups.append(speaker.snapshot_group.copy())

            return groups

        def _restore_players(speakers: list[SonosSpeaker]) -> None:
            """Restore state of all players."""
            for speaker in (s for s in speakers if not s.is_coordinator):
                speaker.restore()

            for speaker in (s for s in speakers if s.is_coordinator):
                speaker.restore()

        # Find all affected players
        speakers_set = {s for s in speakers if s.soco_snapshot}
        if with_group:
            for speaker in [s for s in speakers_set if s.snapshot_group]:
                assert speaker.snapshot_group is not None
                speakers_set.update(speaker.snapshot_group)

        async with hass.data[DATA_SONOS].topology_condition:
            groups = await hass.async_add_executor_job(
                _restore_groups, speakers_set, with_group
            )
            await SonosSpeaker.wait_for_groups(hass, groups)
            await hass.async_add_executor_job(_restore_players, speakers_set)

    @staticmethod
    async def wait_for_groups(
        hass: HomeAssistant, groups: list[list[SonosSpeaker]]
    ) -> None:
        """Wait until all groups are present, or timeout."""

        def _test_groups(groups: list[list[SonosSpeaker]]) -> bool:
            """Return whether all groups exist now."""
            for group in groups:
                coordinator = group[0]

                # Test that coordinator is coordinating
                current_group = coordinator.sonos_group
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

        for speaker in hass.data[DATA_SONOS].discovered.values():
            speaker.soco._zgs_cache.clear()  # pylint: disable=protected-access

    @property
    def favorites(self) -> SonosFavorites:
        """Return the SonosFavorites instance for this household."""
        return self.hass.data[DATA_SONOS].favorites[self.household_id]

    @callback
    def async_update_content(self, event: SonosEvent | None = None) -> None:
        """Update information about available content."""
        if event and "favorites_update_id" in event.variables:
            self.favorites.async_delayed_update(event)

    def update_volume(self) -> None:
        """Update information about current volume settings."""
        self.volume = self.soco.volume
        self.muted = self.soco.mute
        self.night_mode = self.soco.night_mode
        self.dialog_mode = self.soco.dialog_mode

    @callback
    def async_update_volume(self, event: SonosEvent) -> None:
        """Update information about currently volume settings."""
        variables = event.variables

        if "volume" in variables:
            self.volume = int(variables["volume"]["Master"])

        if "mute" in variables:
            self.muted = variables["mute"]["Master"] == "1"

        if "night_mode" in variables:
            self.night_mode = variables["night_mode"] == "1"

        if "dialog_level" in variables:
            self.dialog_mode = variables["dialog_level"] == "1"

        self.async_write_entity_states()

    @callback
    def async_update_media(self, event: SonosEvent | None = None) -> None:
        """Update information about currently playing media."""
        self.hass.async_add_executor_job(self.update_media, event)

    def update_media(self, event: SonosEvent | None = None) -> None:
        """Update information about currently playing media."""
        variables = event and event.variables

        if variables and "transport_state" in variables:
            # If the transport has an error then transport_state will
            # not be set
            new_status = variables["transport_state"]
        else:
            transport_info = self.soco.get_current_transport_info()
            new_status = transport_info["current_transport_state"]

        # Ignore transitions, we should get the target state soon
        if new_status == SONOS_STATE_TRANSITIONING:
            return

        self.media.clear()
        update_position = new_status != self.media.playback_status
        self.media.playback_status = new_status

        if variables and "transport_state" in variables:
            self.media.play_mode = variables["current_play_mode"]
            track_uri = variables["enqueued_transport_uri"]
            music_source = self.soco.music_source_from_uri(track_uri)
        else:
            self.media.play_mode = self.soco.play_mode
            music_source = self.soco.music_source

        if music_source == MUSIC_SRC_TV:
            self.update_media_linein(SOURCE_TV)
        elif music_source == MUSIC_SRC_LINE_IN:
            self.update_media_linein(SOURCE_LINEIN)
        else:
            track_info = self.soco.get_current_track_info()
            if not track_info["uri"]:
                self.media.clear_position()
            else:
                self.media.uri = track_info["uri"]
                self.media.artist = track_info.get("artist")
                self.media.album_name = track_info.get("album")
                self.media.title = track_info.get("title")

                if music_source == MUSIC_SRC_RADIO:
                    self.update_media_radio(variables)
                else:
                    self.update_media_music(update_position, track_info)

        self.write_entity_states()

        # Also update slaves
        speakers = self.hass.data[DATA_SONOS].discovered.values()
        for speaker in speakers:
            if speaker.coordinator == self:
                speaker.write_entity_states()

    def update_media_linein(self, source: str) -> None:
        """Update state when playing from line-in/tv."""
        self.media.clear_position()

        self.media.title = source
        self.media.source_name = source

    def update_media_radio(self, variables: dict | None) -> None:
        """Update state when streaming radio."""
        self.media.clear_position()

        try:
            album_art_uri = variables["current_track_meta_data"].album_art_uri
            self.media.image_url = self.media.library.build_album_art_full_uri(
                album_art_uri
            )
        except (TypeError, KeyError, AttributeError):
            pass

        if not self.media.artist:
            try:
                self.media.artist = variables["current_track_meta_data"].creator
            except (KeyError, AttributeError):
                pass

        # Radios without tagging can have part of the radio URI as title.
        # In this case we try to use the radio name instead.
        try:
            uri_meta_data = variables["enqueued_transport_uri_meta_data"]
            if isinstance(uri_meta_data, DidlAudioBroadcast) and (
                self.soco.music_source_from_uri(self.media.title) == MUSIC_SRC_RADIO
                or (
                    isinstance(self.media.title, str)
                    and isinstance(self.media.uri, str)
                    and (
                        self.media.title in self.media.uri
                        or self.media.title in urllib.parse.unquote(self.media.uri)
                    )
                )
            ):
                self.media.title = uri_meta_data.title
        except (TypeError, KeyError, AttributeError):
            pass

        media_info = self.soco.get_current_media_info()

        self.media.channel = media_info["channel"]

        # Check if currently playing radio station is in favorites
        for fav in self.favorites:
            if fav.reference.get_uri() == media_info["uri"]:
                self.media.source_name = fav.title

    def update_media_music(self, update_media_position: bool, track_info: dict) -> None:
        """Update state when playing music tracks."""
        self.media.duration = _timespan_secs(track_info.get("duration"))
        current_position = _timespan_secs(track_info.get("position"))

        # player started reporting position?
        if current_position is not None and self.media.position is None:
            update_media_position = True

        # position jumped?
        if current_position is not None and self.media.position is not None:
            if self.media.playback_status == SONOS_STATE_PLAYING:
                assert self.media.position_updated_at is not None
                time_delta = dt_util.utcnow() - self.media.position_updated_at
                time_diff = time_delta.total_seconds()
            else:
                time_diff = 0

            calculated_position = self.media.position + time_diff

            if abs(calculated_position - current_position) > 1.5:
                update_media_position = True

        if current_position is None:
            self.media.clear_position()
        elif update_media_position:
            self.media.position = current_position
            self.media.position_updated_at = dt_util.utcnow()

        self.media.image_url = track_info.get("album_art")

        playlist_position = int(track_info.get("playlist_position"))  # type: ignore
        if playlist_position > 0:
            self.media.queue_position = playlist_position - 1
