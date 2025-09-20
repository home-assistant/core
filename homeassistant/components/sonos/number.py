"""Entity representing a Sonos number control."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
import time
from typing import cast

from soco.core import SoCo
from soco.exceptions import SoCoException

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import (
    SONOS_CREATE_LEVELS,
    SONOS_GROUP_VOLUME_REFRESHED,
    SONOS_GROUP_VOLUME_REQUEST,
    SONOS_SPEAKER_ACTIVITY,
    SONOS_STATE_UPDATED,
)
from .entity import SonosEntity
from .helpers import SonosConfigEntry, soco_error
from .speaker import SonosSpeaker

LEVEL_TYPES = {
    "audio_delay": (0, 5),
    "bass": (-10, 10),
    "balance": (-100, 100),
    "treble": (-10, 10),
    "sub_crossover": (50, 110),
    "sub_gain": (-15, 15),
    "surround_level": (-15, 15),
    "music_surround_level": (-15, 15),
}

GV_REFRESH_DELAY = 0.5  # seconds to coalesce group-volume refresh after events

type SocoFeatures = list[tuple[str, tuple[int, int]]]

_LOGGER = logging.getLogger(__name__)


def _gv_signal(group_uid: str) -> str:
    return f"{SONOS_GROUP_VOLUME_REFRESHED}-{group_uid}"


def _gv_req_signal(group_uid: str) -> str:
    return f"{SONOS_GROUP_VOLUME_REQUEST}-{group_uid}"


def _balance_to_number(state: tuple[int, int]) -> float:
    """Represent a balance measure returned by SoCo as a number.

    SoCo returns a pair of volumes, one for the left side and one
    for the right side. When the two are equal, sound is centered;
    HA will show that as 0. When the left side is louder, HA will
    show a negative value, and a positive value means the right
    side is louder. Maximum absolute value is 100, which means only
    one side produces sound at all.
    """
    left, right = state
    return (right - left) * 100 // max(right, left)


def _balance_from_number(value: float) -> tuple[int, int]:
    """Convert a balance value from -100 to 100 into SoCo format.

    0 becomes (100, 100), fully enabling both sides. Note that
    the master volume control is separate, so this does not
    turn up the speakers to maximum volume. Negative values
    reduce the volume of the right side, and positive values
    reduce the volume of the left side. -100 becomes (100, 0),
    fully muting the right side, and +100 becomes (0, 100),
    muting the left side.
    """
    left = min(100, 100 - int(value))
    right = min(100, int(value) + 100)
    return left, right


LEVEL_TO_NUMBER = {"balance": _balance_to_number}
LEVEL_FROM_NUMBER = {"balance": _balance_from_number}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SonosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sonos number platform from a config entry."""

    def available_soco_attributes(speaker: SonosSpeaker) -> SocoFeatures:
        features: SocoFeatures = []
        for level_type, valid_range in LEVEL_TYPES.items():
            if (state := getattr(speaker.soco, level_type, None)) is not None:
                setattr(speaker, level_type, state)
                features.append((level_type, valid_range))
        return features

    async def _async_create_entities(speaker: SonosSpeaker) -> None:
        entities: list[NumberEntity] = []

        available_features = await hass.async_add_executor_job(
            available_soco_attributes, speaker
        )

        for level_type, valid_range in available_features:
            _LOGGER.debug(
                "Creating %s number control on %s", level_type, speaker.zone_name
            )
            entities.append(
                SonosLevelEntity(speaker, config_entry, level_type, valid_range)
            )

        # Native Sonos group volume (0–100); when ungrouped, mirrors player volume
        entities.append(SonosGroupVolumeEntity(speaker, config_entry))

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SONOS_CREATE_LEVELS, _async_create_entities)
    )


class SonosLevelEntity(SonosEntity, NumberEntity):
    """Representation of a Sonos level entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        speaker: SonosSpeaker,
        config_entry: SonosConfigEntry,
        level_type: str,
        valid_range: tuple[int, int],
    ) -> None:
        """Initialize the level entity."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-{level_type}"
        self._attr_translation_key = level_type
        self.level_type = level_type
        self._attr_native_min_value, self._attr_native_max_value = valid_range

    async def _async_fallback_poll(self) -> None:
        """Poll the value if subscriptions are not working."""
        await self.hass.async_add_executor_job(self.poll_state)

    @soco_error()
    def poll_state(self) -> None:
        """Poll the device for the current state."""
        state = getattr(self.soco, self.level_type)
        setattr(self.speaker, self.level_type, state)

    @soco_error()
    def set_native_value(self, value: float) -> None:
        """Set a new value."""
        from_number = LEVEL_FROM_NUMBER.get(self.level_type, int)
        setattr(self.soco, self.level_type, from_number(value))

    @property
    def native_value(self) -> float:
        """Return the current value."""
        to_number = LEVEL_TO_NUMBER.get(self.level_type, int)
        return cast(float, to_number(getattr(self.speaker, self.level_type)))


class SonosGroupVolumeEntity(SonosEntity, NumberEntity):
    """Group volume (0–100) for the player’s current group.

    - Grouped: uses GroupRenderingControl to read/write group volume.
    - Ungrouped: mirrors the player’s RenderingControl Master volume.
    """

    _attr_translation_key = "group_volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, speaker: SonosSpeaker, config_entry: SonosConfigEntry) -> None:
        """Initialize the Sonos group volume number entity."""
        super().__init__(speaker, config_entry)
        self._attr_unique_id = f"{self.soco.uid}-group_volume"

        self._coord_uid: str | None = None
        self._group_uid: str | None = None

        self._unsubscribe_coord: Callable[[], None] | None = None
        self._unsubscribe_member: Callable[[], None] | None = None
        self._unsubscribe_activity: Callable[[], None] | None = None
        self._unsubscribe_gv_signal: Callable[[], None] | None = None
        self._unsubscribe_gv_req: Callable[[], None] | None = None
        self._delay_unsubscribe: Callable[[], None] | None = None

        self._value: int | None = None
        self._last_rebind_time: float = 0.0
        self._bootstrap: bool = True  # startup settling window

    def _coordinator_soco(self) -> SoCo:
        """Return the coordinator SoCo for this speaker."""
        return (self.speaker.coordinator or self.speaker).soco

    def _current_group_uid(self) -> str | None:
        group = getattr(self._coordinator_soco(), "group", None)
        return getattr(group, "uid", None)

    def _is_grouped(self) -> bool:
        """Return True if this speaker is currently grouped with others."""
        if (group := getattr(self._coordinator_soco(), "group", None)) and (
            members := getattr(group, "members", None)
        ):
            return len(members) > 1
        return False

    def _is_coordinator(self) -> bool:
        return (self.speaker.coordinator or self.speaker).uid == self.speaker.uid

    def _schedule_delayed_refresh(self, seconds: float = GV_REFRESH_DELAY) -> None:
        """Schedule a short delayed refresh on the HA loop (thread-safe)."""

        def _schedule() -> None:
            # Cancel any pending timer
            if self._delay_unsubscribe is not None:
                self._delay_unsubscribe()
                self._delay_unsubscribe = None

            loop = self.hass.loop
            if not loop.is_running() or loop.is_closed():
                return

            async def _delayed_refresh(_now: datetime) -> None:
                self._delay_unsubscribe = None
                self._rebind_for_topology_change()

                await self._async_refresh_from_device()
                self._bootstrap = False

            self._delay_unsubscribe = async_call_later(
                self.hass, seconds, _delayed_refresh
            )

        # If we're already on the loop, call directly; otherwise hop to it safely.
        try:
            running = (
                self.hass.loop.is_running()
                and asyncio.get_running_loop() is self.hass.loop
            )
        except RuntimeError:
            running = False
        if running:
            _schedule()
        else:
            # Ensure scheduling runs on the HA loop thread (not an executor)
            self.hass.loop.call_soon_threadsafe(_schedule)

    async def _async_initial_populate(self) -> None:
        """One-time populate before the coordinator fans out values."""
        if self._is_grouped():
            # Read the coordinator's group volume directly
            def _get_group() -> int | None:
                try:
                    return int(self._coordinator_soco().group.volume)
                except (SoCoException, OSError) as err:
                    _LOGGER.debug(
                        "Initial populate: failed group volume for %s: %s",
                        self.speaker.zone_name,
                        err,
                    )
                    return None

            vol = await self.hass.async_add_executor_job(_get_group)
        else:

            def _get_player() -> int | None:
                try:
                    return int(self.soco.volume)
                except (SoCoException, OSError) as err:
                    _LOGGER.debug(
                        "Initial populate: failed player volume for %s: %s",
                        self.speaker.zone_name,
                        err,
                    )
                    return None

            vol = await self.hass.async_add_executor_job(_get_player)

        if vol is not None and self._value != vol:
            self._value = vol
            self.async_write_ha_state()

    def _subscribe_group_fanout(self, group_uid: str | None) -> None:
        """Subscribe to the current group’s fan-out signal."""
        if self._unsubscribe_gv_signal is not None:
            self._unsubscribe_gv_signal()
            self._unsubscribe_gv_signal = None
        if group_uid:
            self._unsubscribe_gv_signal = async_dispatcher_connect(
                self.hass, _gv_signal(group_uid), self._on_group_volume_fanned
            )
            self.async_on_remove(self._unsubscribe_gv_signal)

    def _subscribe_group_requests_if_coord(self, group_uid: str | None) -> None:
        """If coordinator, subscribe for group refresh requests."""
        if self._unsubscribe_gv_req is not None:
            self._unsubscribe_gv_req()
            self._unsubscribe_gv_req = None
        if group_uid and self._is_grouped() and self._is_coordinator():
            self._unsubscribe_gv_req = async_dispatcher_connect(
                self.hass, _gv_req_signal(group_uid), self._on_group_volume_request
            )
            self.async_on_remove(self._unsubscribe_gv_req)

    def _rebind_for_topology_change(self) -> None:
        """Re-evaluate coordinator/group, rebind signals, and refresh as needed."""
        now = time.monotonic()
        old_grouped = self._is_grouped()
        old_coord_flag = self._is_coordinator()
        new_coord_uid = (self.speaker.coordinator or self.speaker).uid
        new_group_uid = self._current_group_uid()
        no_change = (
            new_coord_uid == self._coord_uid
            and new_group_uid == self._group_uid
            and old_grouped == self._is_grouped()
            and old_coord_flag == self._is_coordinator()
        )
        # If nothing changed, there's nothing to rebind.
        if no_change:
            return
        # Coalesce true topology changes (prevent rapid unsubscribe/resubscribe churn).
        if (now - self._last_rebind_time) < (GV_REFRESH_DELAY * 2):
            return

        # Always ensure we listen to our own member state
        if self._unsubscribe_member is None:
            self._unsubscribe_member = async_dispatcher_connect(
                self.hass,
                f"{SONOS_STATE_UPDATED}-{self.speaker.uid}",
                self._on_member_state_updated,
            )
            self.async_on_remove(self._unsubscribe_member)

        # Group binding
        if new_group_uid != self._group_uid:
            self._group_uid = new_group_uid
            self._subscribe_group_fanout(new_group_uid)

        # (Re)bind coordinator-request listener if we are coordinator
        self._subscribe_group_requests_if_coord(new_group_uid)

        self._last_rebind_time = time.monotonic()

        if self._is_grouped():
            if self._is_coordinator():
                self._schedule_delayed_refresh(GV_REFRESH_DELAY)
            elif new_group_uid:
                # Post request on the HA loop from any thread safely
                self.hass.loop.call_soon_threadsafe(
                    async_dispatcher_send,
                    self.hass,
                    _gv_req_signal(new_group_uid),
                    None,
                )
                self._schedule_delayed_refresh(GV_REFRESH_DELAY)
        else:
            # Ungrouped: drop group listeners and mirror the player’s own volume
            if self._unsubscribe_gv_req is not None:
                self._unsubscribe_gv_req()
                self._unsubscribe_gv_req = None
            if self._unsubscribe_gv_signal is not None:
                self._unsubscribe_gv_signal()
                self._unsubscribe_gv_signal = None
            # Schedule refresh on the HA loop safely
            self.hass.loop.call_soon_threadsafe(
                self.hass.async_create_task, self._async_refresh_from_device()
            )

    @property
    def native_value(self) -> float | None:
        """Return the current group volume (0–100) or None if unknown."""
        return None if self._value is None else float(self._value)

    @soco_error()
    def set_native_value(self, value: float) -> None:
        """Set the group volume (0–100), or player volume when ungrouped."""
        level = int(value + 0.5)
        if self._is_grouped():
            coord = self._coordinator_soco()
            coord.group.volume = level
            if group_uid := self._current_group_uid():
                # Post a fan-out request on the HA loop
                self.hass.loop.call_soon_threadsafe(
                    async_dispatcher_send,
                    self.hass,
                    _gv_req_signal(group_uid),
                    None,
                )
                self._schedule_delayed_refresh(GV_REFRESH_DELAY)
        else:
            self.soco.volume = level

    async def _async_fallback_poll(self) -> None:
        """Fallback polling path when event subscriptions are unavailable."""
        await self._async_refresh_from_device()

    async def _async_refresh_from_device(self) -> None:
        """Read the current volume (group if grouped, else player) and propagate to peers."""
        group_uid_actual = self._current_group_uid()

        if self._is_grouped():
            if not self._is_coordinator():
                return  # coordinator is authoritative and will fan-out

            def _get_group() -> int | None:
                try:
                    return int(self._coordinator_soco().group.volume)
                except (SoCoException, OSError) as err:
                    _LOGGER.debug(
                        "Failed to read group volume for %s: %s",
                        self.speaker.zone_name,
                        err,
                    )
                    return None

            if (vol := await self.hass.async_add_executor_job(_get_group)) is None:
                return

            if self._value != vol:
                self._value = vol
                self.async_write_ha_state()
                if group_uid_actual:
                    # Fan-out to members (thread-safe via dispatcher)
                    self.hass.loop.call_soon_threadsafe(
                        async_dispatcher_send,
                        self.hass,
                        _gv_signal(group_uid_actual),
                        (group_uid_actual, vol),
                    )
            return

        def _get_player() -> int | None:
            try:
                return int(self.soco.volume)
            except (SoCoException, OSError) as err:
                _LOGGER.debug(
                    "Failed to read player volume for %s: %s",
                    self.speaker.zone_name,
                    err,
                )
                return None

        if (vol := await self.hass.async_add_executor_job(_get_player)) is None:
            return

        if self._value != vol:
            self._value = vol
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Bind signals, perform initial populate/refresh, and start subscriptions."""
        await super().async_added_to_hass()

        # Listen for any speaker activity
        self._unsubscribe_activity = async_dispatcher_connect(
            self.hass, SONOS_SPEAKER_ACTIVITY, self._on_any_activity
        )
        self.async_on_remove(self._unsubscribe_activity)

        # Rebind subscriptions and topology links
        self._rebind_for_topology_change()

        # Bootstrap: populate initial value, then schedule a delayed settle refresh
        await self._async_initial_populate()
        self._schedule_delayed_refresh(GV_REFRESH_DELAY)

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup on removal (dispatcher unsubs handled elsewhere; cancel pending timer)."""
        await super().async_will_remove_from_hass()

        # Let async_on_remove(...) handle dispatcher unsubs; just cancel timer
        if self._delay_unsubscribe is not None:
            self._delay_unsubscribe()
            self._delay_unsubscribe = None

    @callback
    def _on_group_volume_request(self, *_: object) -> None:
        """Coordinator-only: handle a member’s request to refresh group volume."""
        if not (self._is_grouped() and self._is_coordinator()):
            return
        self._schedule_delayed_refresh(GV_REFRESH_DELAY)

    @callback
    def _on_coord_state_updated(self, *_: object) -> None:
        """Coordinator state changed; re-evaluate bindings and schedule refresh if needed."""
        self._rebind_for_topology_change()

    @callback
    def _on_member_state_updated(self, *_: object) -> None:
        """Member state changed; rebind and trigger the appropriate refresh path."""
        self._rebind_for_topology_change()

    @callback
    def _on_group_volume_fanned(self, payload: tuple[str, int]) -> None:
        """Apply coordinator’s fanned group volume if the payload matches our current group."""
        group_uid, level = payload
        current_group_uid = self._current_group_uid()
        if group_uid != current_group_uid:
            self._rebind_for_topology_change()
            return
        if not self._is_grouped():
            return
        if self._value != level:
            self._value = level
            self.async_write_ha_state()

    @callback
    def _on_any_activity(self, *_: object) -> None:
        """Any speaker activity — rebind if coordinator/group changed, then refresh."""
        self._rebind_for_topology_change()
