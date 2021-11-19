"""Base class for common speaker tasks."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import contextlib
import datetime
from functools import partial
import logging
import time
from typing import Any
import urllib.parse

import async_timeout
from soco.core import MUSIC_SRC_LINE_IN, MUSIC_SRC_RADIO, MUSIC_SRC_TV, SoCo
from soco.data_structures import DidlAudioBroadcast, DidlPlaylistContainer
from soco.events_base import Event as SonosEvent, SubscriptionBase
from soco.exceptions import SoCoException, SoCoSlaveException, SoCoUPnPException
from soco.music_library import MusicLibrary
from soco.plugins.sharelink import ShareLinkPlugin
from soco.snapshot import Snapshot

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as ent_reg
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
    dispatcher_send,
)
from homeassistant.util import dt as dt_util

from .alarms import SonosAlarms
from .const import (
    AVAILABILITY_TIMEOUT,
    BATTERY_SCAN_INTERVAL,
    DATA_SONOS,
    DOMAIN,
    PLATFORMS,
    SCAN_INTERVAL,
    SONOS_CHECK_ACTIVITY,
    SONOS_CREATE_ALARM,
    SONOS_CREATE_BATTERY,
    SONOS_CREATE_MEDIA_PLAYER,
    SONOS_CREATE_SWITCHES,
    SONOS_ENTITY_CREATED,
    SONOS_POLL_UPDATE,
    SONOS_REBOOTED,
    SONOS_SPEAKER_ACTIVITY,
    SONOS_SPEAKER_ADDED,
    SONOS_STATE_PLAYING,
    SONOS_STATE_TRANSITIONING,
    SONOS_STATE_UPDATED,
    SOURCE_LINEIN,
    SOURCE_TV,
    SUBSCRIPTION_TIMEOUT,
)
from .favorites import SonosFavorites
from .helpers import soco_error

EVENT_CHARGING = {
    "CHARGING": True,
    "NOT_CHARGING": False,
}
SUBSCRIPTION_SERVICES = [
    "alarmClock",
    "avTransport",
    "contentDirectory",
    "deviceProperties",
    "renderingControl",
    "zoneGroupTopology",
]
UNAVAILABLE_VALUES = {"", "NOT_IMPLEMENTED", None}
UNUSED_DEVICE_KEYS = ["SPID", "TargetRoomName"]


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
        self.playlist_name: str | None = None
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
        self.playlist_name = None
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
        self._share_link_plugin: ShareLinkPlugin | None = None
        self.available = True

        # Synchronization helpers
        self._is_ready: bool = False
        self._platforms_ready: set[str] = set()

        # Subscriptions and events
        self.subscriptions_failed: bool = False
        self._subscriptions: list[SubscriptionBase] = []
        self._resubscription_lock: asyncio.Lock | None = None
        self._event_dispatchers: dict[str, Callable] = {}
        self._last_activity: datetime.datetime | None = None

        # Scheduled callback handles
        self._poll_timer: Callable | None = None

        # Dispatcher handles
        self.dispatchers: list[Callable] = []

        # Device information
        self.mac_address = speaker_info["mac_address"]
        self.model_name = speaker_info["model_name"]
        self.uid = speaker_info["uid"]
        self.version = speaker_info["display_version"]
        self.zone_name = speaker_info["zone_name"]

        # Battery
        self.battery_info: dict[str, Any] = {}
        self._last_battery_event: datetime.datetime | None = None
        self._battery_poll_timer: Callable | None = None

        # Volume / Sound
        self.volume: int | None = None
        self.muted: bool | None = None
        self.night_mode: bool | None = None
        self.dialog_mode: bool | None = None
        self.cross_fade: bool | None = None
        self.bass_level: int | None = None
        self.treble_level: int | None = None

        # Misc features
        self.buttons_enabled: bool | None = None
        self.status_light: bool | None = None

        # Grouping
        self.coordinator: SonosSpeaker | None = None
        self.sonos_group: list[SonosSpeaker] = [self]
        self.sonos_group_entities: list[str] = []
        self.soco_snapshot: Snapshot | None = None
        self.snapshot_group: list[SonosSpeaker] | None = None
        self._group_members_missing: set[str] = set()

    async def async_setup_dispatchers(self, entry: ConfigEntry) -> None:
        """Connect dispatchers in async context during setup."""
        dispatch_pairs = (
            (SONOS_CHECK_ACTIVITY, self.async_check_activity),
            (SONOS_SPEAKER_ADDED, self.update_group_for_uid),
            (f"{SONOS_ENTITY_CREATED}-{self.soco.uid}", self.async_handle_new_entity),
            (f"{SONOS_REBOOTED}-{self.soco.uid}", self.async_rebooted),
            (f"{SONOS_SPEAKER_ACTIVITY}-{self.soco.uid}", self.speaker_activity),
        )

        for (signal, target) in dispatch_pairs:
            entry.async_on_unload(
                async_dispatcher_connect(
                    self.hass,
                    signal,
                    target,
                )
            )

    def setup(self, entry: ConfigEntry) -> None:
        """Run initial setup of the speaker."""
        self.set_basic_info()
        future = asyncio.run_coroutine_threadsafe(
            self.async_setup_dispatchers(entry), self.hass.loop
        )
        future.result(timeout=10)

        if battery_info := fetch_battery_info_or_none(self.soco):
            self.battery_info = battery_info
            # Battery events can be infrequent, polling is still necessary
            self._battery_poll_timer = self.hass.helpers.event.track_time_interval(
                self.async_poll_battery, BATTERY_SCAN_INTERVAL
            )
            dispatcher_send(self.hass, SONOS_CREATE_BATTERY, self)
        else:
            self._platforms_ready.update({BINARY_SENSOR_DOMAIN, SENSOR_DOMAIN})

        if new_alarms := [
            alarm.alarm_id for alarm in self.alarms if alarm.zone.uid == self.soco.uid
        ]:
            dispatcher_send(self.hass, SONOS_CREATE_ALARM, self, new_alarms)
        else:
            self._platforms_ready.add(SWITCH_DOMAIN)

        dispatcher_send(self.hass, SONOS_CREATE_SWITCHES, self)

        self._event_dispatchers = {
            "AlarmClock": self.async_dispatch_alarms,
            "AVTransport": self.async_dispatch_media_update,
            "ContentDirectory": self.async_dispatch_favorites,
            "DeviceProperties": self.async_dispatch_device_properties,
            "RenderingControl": self.async_update_volume,
            "ZoneGroupTopology": self.async_update_groups,
        }

        dispatcher_send(self.hass, SONOS_CREATE_MEDIA_PLAYER, self)
        dispatcher_send(self.hass, SONOS_SPEAKER_ADDED, self.soco.uid)

    #
    # Entity management
    #
    async def async_handle_new_entity(self, entity_type: str) -> None:
        """Listen to new entities to trigger first subscription."""
        if self._platforms_ready == PLATFORMS:
            return

        self._platforms_ready.add(entity_type)
        if self._platforms_ready == PLATFORMS:
            self._resubscription_lock = asyncio.Lock()
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

    #
    # Properties
    #
    @property
    def alarms(self) -> SonosAlarms:
        """Return the SonosAlarms instance for this household."""
        return self.hass.data[DATA_SONOS].alarms[self.household_id]

    @property
    def favorites(self) -> SonosFavorites:
        """Return the SonosFavorites instance for this household."""
        return self.hass.data[DATA_SONOS].favorites[self.household_id]

    @property
    def is_coordinator(self) -> bool:
        """Return true if player is a coordinator."""
        return self.coordinator is None

    @property
    def share_link(self) -> ShareLinkPlugin:
        """Cache the ShareLinkPlugin instance for this speaker."""
        if not self._share_link_plugin:
            self._share_link_plugin = ShareLinkPlugin(self.soco)
        return self._share_link_plugin

    @property
    def subscription_address(self) -> str | None:
        """Return the current subscription callback address if any."""
        if self._subscriptions:
            addr, port = self._subscriptions[0].event_listener.address
            return ":".join([addr, str(port)])
        return None

    #
    # Subscription handling and event dispatchers
    #
    async def async_subscribe(self) -> bool:
        """Initiate event subscriptions."""
        _LOGGER.debug("Creating subscriptions for %s", self.zone_name)

        # Create a polling task in case subscriptions fail or callback events do not arrive
        if not self._poll_timer:
            self._poll_timer = self.hass.helpers.event.async_track_time_interval(
                partial(
                    async_dispatcher_send,
                    self.hass,
                    f"{SONOS_POLL_UPDATE}-{self.soco.uid}",
                ),
                SCAN_INTERVAL,
            )

        try:
            await self.hass.async_add_executor_job(self.set_basic_info)

            if self._subscriptions:
                raise RuntimeError(
                    f"Attempted to attach subscriptions to player: {self.soco} "
                    f"when existing subscriptions exist: {self._subscriptions}"
                )

            subscriptions = [
                self._subscribe(getattr(self.soco, service), self.async_dispatch_event)
                for service in SUBSCRIPTION_SERVICES
            ]
            await asyncio.gather(*subscriptions)
        except SoCoException as ex:
            _LOGGER.warning("Could not connect %s: %s", self.zone_name, ex)
            return False
        return True

    async def _subscribe(
        self, target: SubscriptionBase, sub_callback: Callable
    ) -> None:
        """Create a Sonos subscription."""
        subscription = await target.subscribe(
            auto_renew=True, requested_timeout=SUBSCRIPTION_TIMEOUT
        )
        subscription.callback = sub_callback
        subscription.auto_renew_fail = self.async_renew_failed
        self._subscriptions.append(subscription)

    async def async_unsubscribe(self) -> None:
        """Cancel all subscriptions."""
        _LOGGER.debug("Unsubscribing from events for %s", self.zone_name)
        results = await asyncio.gather(
            *(subscription.unsubscribe() for subscription in self._subscriptions),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                _LOGGER.debug("Unsubscribe failed for %s: %s", self.zone_name, result)
        self._subscriptions = []

    @callback
    def async_renew_failed(self, exception: Exception) -> None:
        """Handle a failed subscription renewal."""
        self.hass.async_create_task(self.async_resubscribe(exception))

    async def async_resubscribe(self, exception: Exception) -> None:
        """Attempt to resubscribe when a renewal failure is detected."""
        async with self._resubscription_lock:
            if not self.available:
                return

            if getattr(exception, "status", None) == 412:
                _LOGGER.warning(
                    "Subscriptions for %s failed, speaker may have lost power",
                    self.zone_name,
                )
            else:
                _LOGGER.error(
                    "Subscription renewals for %s failed",
                    self.zone_name,
                    exc_info=exception,
                )
            await self.async_offline()

    @callback
    def async_dispatch_event(self, event: SonosEvent) -> None:
        """Handle callback event and route as needed."""
        if self._poll_timer:
            _LOGGER.debug(
                "Received event, cancelling poll timer for %s", self.zone_name
            )
            self._poll_timer()
            self._poll_timer = None

        self.speaker_activity(f"{event.service.service_type} subscription")

        dispatcher = self._event_dispatchers[event.service.service_type]
        dispatcher(event)

    @callback
    def async_dispatch_alarms(self, event: SonosEvent) -> None:
        """Add the soco instance associated with the event to the callback."""
        if not (event_id := event.variables.get("alarm_list_version")):
            return
        self.alarms.async_handle_event(event_id, self.soco)

    @callback
    def async_dispatch_device_properties(self, event: SonosEvent) -> None:
        """Update device properties from an event."""
        self.hass.async_create_task(self.async_update_device_properties(event))

    async def async_update_device_properties(self, event: SonosEvent) -> None:
        """Update device properties from an event."""
        if more_info := event.variables.get("more_info"):
            battery_dict = dict(x.split(":") for x in more_info.split(","))
            for unused in UNUSED_DEVICE_KEYS:
                battery_dict.pop(unused, None)
            if not battery_dict:
                return
            if "BattChg" not in battery_dict:
                _LOGGER.debug(
                    "Unknown device properties update for %s (%s), please report an issue: '%s'",
                    self.zone_name,
                    self.model_name,
                    more_info,
                )
                return
            await self.async_update_battery_info(battery_dict)
        self.async_write_entity_states()

    @callback
    def async_dispatch_favorites(self, event: SonosEvent) -> None:
        """Add the soco instance associated with the event to the callback."""
        if not (event_id := event.variables.get("favorites_update_id")):
            return
        if not (container_ids := event.variables.get("container_update_i_ds")):
            return
        self.favorites.async_handle_event(event_id, container_ids, self.soco)

    @callback
    def async_dispatch_media_update(self, event: SonosEvent) -> None:
        """Update information about currently playing media from an event."""
        if crossfade := event.variables.get("current_crossfade_mode"):
            self.cross_fade = bool(int(crossfade))

        self.hass.async_add_executor_job(self.update_media, event)

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

        if "bass_level" in variables:
            self.bass_level = variables["bass_level"]

        if "treble_level" in variables:
            self.treble_level = variables["treble_level"]

        self.async_write_entity_states()

    #
    # Speaker availability methods
    #
    @callback
    def speaker_activity(self, source):
        """Track the last activity on this speaker, set availability and resubscribe."""
        _LOGGER.debug("Activity on %s from %s", self.zone_name, source)
        self._last_activity = time.monotonic()
        was_available = self.available
        self.available = True
        if not was_available:
            self.async_write_entity_states()
            self.hass.async_create_task(self.async_subscribe())

    async def async_check_activity(self, now: datetime.datetime) -> None:
        """Validate availability of the speaker based on recent activity."""
        if time.monotonic() - self._last_activity < AVAILABILITY_TIMEOUT:
            return

        try:
            _ = await self.hass.async_add_executor_job(getattr, self.soco, "volume")
        except (OSError, SoCoException):
            pass
        else:
            self.speaker_activity("timeout poll")
            return

        if not self.available:
            return

        _LOGGER.debug(
            "No recent activity and cannot reach %s, marking unavailable",
            self.zone_name,
        )
        await self.async_offline()

    async def async_offline(self) -> None:
        """Handle removal of speaker when unavailable."""
        self.available = False
        self._share_link_plugin = None

        if self._poll_timer:
            self._poll_timer()
            self._poll_timer = None

        await self.async_unsubscribe()

        self.hass.data[DATA_SONOS].discovery_known.discard(self.soco.uid)
        self.async_write_entity_states()

    async def async_rebooted(self, soco: SoCo) -> None:
        """Handle a detected speaker reboot."""
        _LOGGER.warning(
            "%s rebooted or lost network connectivity, reconnecting with %s",
            self.zone_name,
            soco,
        )
        await self.async_offline()
        self.soco = soco
        self.speaker_activity("reboot")

    #
    # Battery management
    #
    async def async_update_battery_info(self, battery_dict: dict[str, Any]) -> None:
        """Update battery info using the decoded SonosEvent."""
        self._last_battery_event = dt_util.utcnow()

        is_charging = EVENT_CHARGING[battery_dict["BattChg"]]

        if not self._battery_poll_timer:
            # Battery info received for an S1 speaker
            new_battery = not self.battery_info
            self.battery_info.update(
                {
                    "Level": int(battery_dict["BattPct"]),
                    "PowerSource": "EXTERNAL" if is_charging else "BATTERY",
                }
            )
            if new_battery:
                _LOGGER.warning(
                    "S1 firmware detected on %s, battery info may update infrequently",
                    self.zone_name,
                )
                async_dispatcher_send(self.hass, SONOS_CREATE_BATTERY, self)
            return

        if is_charging == self.charging:
            self.battery_info.update({"Level": int(battery_dict["BattPct"])})
        else:
            if battery_info := await self.hass.async_add_executor_job(
                fetch_battery_info_or_none, self.soco
            ):
                self.battery_info = battery_info

    @property
    def power_source(self) -> str | None:
        """Return the name of the current power source.

        Observed to be either BATTERY or SONOS_CHARGING_RING or USB_POWER.

        May be an empty dict if used with an S1 Move.
        """
        return self.battery_info.get("PowerSource")

    @property
    def charging(self) -> bool | None:
        """Return the charging status of the speaker."""
        if self.power_source:
            return self.power_source != "BATTERY"
        return None

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

    #
    # Group management
    #
    def update_groups(self) -> None:
        """Update group topology when polling."""
        self.hass.add_job(self.create_update_groups_coro())

    def update_group_for_uid(self, uid: str) -> None:
        """Update group topology if uid is missing."""
        if uid not in self._group_members_missing:
            return
        missing_zone = self.hass.data[DATA_SONOS].discovered[uid].zone_name
        _LOGGER.debug(
            "%s was missing, adding to %s group", missing_zone, self.zone_name
        )
        self.update_groups()

    @callback
    def async_update_groups(self, event: SonosEvent) -> None:
        """Handle callback for topology change event."""
        if not hasattr(event, "zone_player_uui_ds_in_group"):
            return
        self.hass.async_create_task(self.create_update_groups_coro(event))

    def create_update_groups_coro(self, event: SonosEvent | None = None) -> Coroutine:
        """Handle callback for topology change event."""

        def _get_soco_group() -> list[str]:
            """Ask SoCo cache for existing topology."""
            coordinator_uid = self.soco.uid
            slave_uids = []

            with contextlib.suppress(OSError, SoCoException):
                if self.soco.group and self.soco.group.coordinator:
                    coordinator_uid = self.soco.group.coordinator.uid
                    slave_uids = [
                        p.uid
                        for p in self.soco.group.members
                        if p.uid != coordinator_uid and p.is_visible
                    ]

            return [coordinator_uid] + slave_uids

        async def _async_extract_group(event: SonosEvent | None) -> list[str]:
            """Extract group layout from a topology event."""
            group = event and event.zone_player_uui_ds_in_group
            if group:
                assert isinstance(group, str)
                return group.split(",")

            return await self.hass.async_add_executor_job(_get_soco_group)

        @callback
        def _async_regroup(group: list[str]) -> None:
            """Rebuild internal group layout."""
            if (
                group == [self.soco.uid]
                and self.sonos_group == [self]
                and self.sonos_group_entities
            ):
                # Skip updating existing single speakers in polling mode
                return

            entity_registry = ent_reg.async_get(self.hass)
            sonos_group = []
            sonos_group_entities = []

            for uid in group:
                speaker = self.hass.data[DATA_SONOS].discovered.get(uid)
                if speaker:
                    self._group_members_missing.discard(uid)
                    sonos_group.append(speaker)
                    entity_id = entity_registry.async_get_entity_id(
                        MP_DOMAIN, DOMAIN, uid
                    )
                    sonos_group_entities.append(entity_id)
                else:
                    self._group_members_missing.add(uid)
                    _LOGGER.debug(
                        "%s group member unavailable (%s), will try again",
                        self.zone_name,
                        uid,
                    )

            if self.sonos_group_entities == sonos_group_entities:
                # Useful in polling mode for speakers with stereo pairs or surrounds
                # as those "invisible" speakers will bypass the single speaker check
                return

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

            _LOGGER.debug("Regrouped %s: %s", self.zone_name, self.sonos_group_entities)

        async def _async_handle_group_event(event: SonosEvent | None) -> None:
            """Get async lock and handle event."""

            async with self.hass.data[DATA_SONOS].topology_condition:
                group = await _async_extract_group(event)

                if self.soco.uid == group[0]:
                    _async_regroup(group)

                    self.hass.data[DATA_SONOS].topology_condition.notify_all()

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
            speakers: set[SonosSpeaker], with_group: bool
        ) -> list[list[SonosSpeaker]]:
            """Pause all current coordinators and restore groups."""
            for speaker in (s for s in speakers if s.is_coordinator):
                if (
                    speaker.media.playback_status == SONOS_STATE_PLAYING
                    and "Pause" in speaker.soco.available_actions
                ):
                    try:
                        speaker.soco.pause()
                    except SoCoUPnPException as exc:
                        _LOGGER.debug(
                            "Pause failed during restore of %s: %s",
                            speaker.zone_name,
                            speaker.soco.available_actions,
                            exc_info=exc,
                        )

            groups = []
            if not with_group:
                return groups

            # Unjoin non-coordinator speakers not contained in the desired snapshot group
            #
            # If a coordinator is unjoined from its group, another speaker from the group
            # will inherit the coordinator's playqueue and its own playqueue will be lost
            speakers_to_unjoin = set()
            for speaker in speakers:
                if speaker.sonos_group == speaker.snapshot_group:
                    continue

                speakers_to_unjoin.update(
                    {
                        s
                        for s in speaker.sonos_group[1:]
                        if s not in speaker.snapshot_group
                    }
                )

            for speaker in speakers_to_unjoin:
                speaker.unjoin()

            # Bring back the original group topology
            for speaker in (s for s in speakers if s.snapshot_group):
                assert speaker.snapshot_group is not None
                if speaker.snapshot_group[0] == speaker:
                    if speaker.snapshot_group not in (speaker.sonos_group, [speaker]):
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
        if missing_snapshots := set(speakers) - speakers_set:
            raise HomeAssistantError(
                f"Restore failed, speakers are missing snapshots: {[s.zone_name for s in missing_snapshots]}"
            )

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
            async with async_timeout.timeout(5):
                while not _test_groups(groups):
                    await hass.data[DATA_SONOS].topology_condition.wait()
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout waiting for target groups %s", groups)

        for speaker in hass.data[DATA_SONOS].discovered.values():
            speaker.soco._zgs_cache.clear()  # pylint: disable=protected-access

    #
    # Media and playback state handlers
    #
    def update_volume(self) -> None:
        """Update information about current volume settings."""
        self.volume = self.soco.volume
        self.muted = self.soco.mute
        self.night_mode = self.soco.night_mode
        self.dialog_mode = self.soco.dialog_mode
        self.bass_level = self.soco.bass
        self.treble_level = self.soco.treble

        try:
            self.cross_fade = self.soco.cross_fade
        except SoCoSlaveException:
            pass

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
            track_uri = (
                variables["enqueued_transport_uri"] or variables["current_track_uri"]
            )
            music_source = self.soco.music_source_from_uri(track_uri)
            if uri_meta_data := variables.get("enqueued_transport_uri_meta_data"):
                if isinstance(uri_meta_data, DidlPlaylistContainer):
                    self.media.playlist_name = uri_meta_data.title
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
                    self.update_media_music(track_info)
                self.update_media_position(update_position, track_info)

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
        radio_title = None

        if current_track_metadata := variables.get("current_track_meta_data"):
            if album_art_uri := getattr(current_track_metadata, "album_art_uri", None):
                self.media.image_url = self.media.library.build_album_art_full_uri(
                    album_art_uri
                )
            if not self.media.artist:
                self.media.artist = getattr(current_track_metadata, "creator", None)

            # A missing artist implies metadata is incomplete, try a different method
            if not self.media.artist:
                radio_show = None
                stream_content = None
                if current_track_metadata.radio_show:
                    radio_show = current_track_metadata.radio_show.split(",")[0]
                if not current_track_metadata.stream_content.startswith(
                    ("ZPSTR_", "TYPE=")
                ):
                    stream_content = current_track_metadata.stream_content
                radio_title = " • ".join(filter(None, [radio_show, stream_content]))

        if radio_title:
            # Prefer the radio title created above
            self.media.title = radio_title
        elif uri_meta_data := variables.get("enqueued_transport_uri_meta_data"):
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
                # Fall back to the radio channel name as a last resort
                self.media.title = uri_meta_data.title

        media_info = self.soco.get_current_media_info()
        self.media.channel = media_info["channel"]

        # Check if currently playing radio station is in favorites
        fav = next(
            (
                fav
                for fav in self.favorites
                if fav.reference.get_uri() == media_info["uri"]
            ),
            None,
        )
        if fav:
            self.media.source_name = fav.title

    def update_media_music(self, track_info: dict) -> None:
        """Update state when playing music tracks."""
        self.media.image_url = track_info.get("album_art")

        playlist_position = int(track_info.get("playlist_position"))  # type: ignore
        if playlist_position > 0:
            self.media.queue_position = playlist_position - 1

    def update_media_position(
        self, update_media_position: bool, track_info: dict
    ) -> None:
        """Update state when playing music tracks."""
        self.media.duration = _timespan_secs(track_info.get("duration"))
        current_position = _timespan_secs(track_info.get("position"))

        if self.media.duration == 0:
            self.media.clear_position()
            return

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
