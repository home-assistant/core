"""Tests for the Timer list integration."""

from datetime import datetime, timedelta
from functools import partial
from typing import override

from homeassistant.components.timer_list import (
    DOMAIN,
    TimerFinishAction,
    TimerItem,
    TimerListEntity,
    TimerListEntityFeature,
    TimerListEventType,
    TimerStatus,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util, ulid as ulid_util

from tests.common import MockConfigEntry, MockPlatform, mock_platform

TEST_DOMAIN = "test"

ALL_FEATURES = (
    TimerListEntityFeature.START_TIMER
    | TimerListEntityFeature.PAUSE_TIMER
    | TimerListEntityFeature.CANCEL_TIMER
    | TimerListEntityFeature.ADD_TIME
)

_FINISHED_STATUSES = (TimerStatus.FINISHED, TimerStatus.CANCELLED)


class MockFlow(ConfigFlow):
    """Test flow."""


class MockTimerListEntity(TimerListEntity):
    """Test timer list entity.

    Reimplements the same in-memory storage and scheduling as the
    ``local_timer_list`` platform, so the generic services, websocket API,
    and triggers can be exercised without depending on that integration.
    """

    _attr_supported_features = ALL_FEATURES

    def __init__(self, name: str = "Timers") -> None:
        """Initialize entity."""
        super().__init__()
        self._attr_name = name
        self._timers: dict[str, TimerItem] = {}
        self._cancel_callbacks: dict[str, CALLBACK_TYPE] = {}

    @property
    @override
    def timers(self) -> list[TimerItem]:
        """Return the timers in the list."""
        return list(self._timers.values())

    @override
    async def async_start_timer(
        self,
        *,
        name: str | None,
        duration: timedelta,
        finish_action: TimerFinishAction,
    ) -> str:
        """Create and start a new timer, returning its id."""
        now = dt_util.utcnow()
        timer_id = ulid_util.ulid_now()
        timer = TimerItem(
            timer_id=timer_id,
            name=name,
            status=TimerStatus.ACTIVE,
            finish_action=finish_action,
            duration=duration,
            created_at=now,
            finishes_at=now + duration,
        )
        self._timers[timer_id] = timer
        self._schedule(timer)
        self._notify(TimerListEventType.STARTED, timer)
        return timer_id

    @override
    async def async_pause_timer(self, timer_id: str) -> None:
        """Pause an active timer."""
        timer = self._get_timer(timer_id)
        if timer.status != TimerStatus.ACTIVE or timer.finishes_at is None:
            return
        timer.remaining = max(timedelta(0), timer.finishes_at - dt_util.utcnow())
        timer.finishes_at = None
        timer.status = TimerStatus.PAUSED
        self._unschedule(timer_id)
        self._notify(TimerListEventType.UPDATED, timer)

    @override
    async def async_unpause_timer(self, timer_id: str) -> None:
        """Resume a paused timer."""
        timer = self._get_timer(timer_id)
        if timer.status != TimerStatus.PAUSED or timer.remaining is None:
            return
        timer.finishes_at = dt_util.utcnow() + timer.remaining
        timer.remaining = None
        timer.status = TimerStatus.ACTIVE
        self._schedule(timer)
        self._notify(TimerListEventType.UPDATED, timer)

    @override
    async def async_cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer."""
        timer = self._get_timer(timer_id)
        self._unschedule(timer_id)
        timer.status = TimerStatus.CANCELLED
        timer.finishes_at = None
        timer.remaining = None
        timer.finished_at = dt_util.utcnow()
        self._notify(TimerListEventType.CANCELLED, timer)
        if timer.finish_action != TimerFinishAction.ARCHIVE:
            del self._timers[timer_id]
            self._notify(TimerListEventType.REMOVED, timer)

    @override
    async def async_cancel_all_timers(self) -> None:
        """Cancel every active or paused timer."""
        for timer_id in [
            timer.timer_id
            for timer in self._timers.values()
            if timer.status in (TimerStatus.ACTIVE, TimerStatus.PAUSED)
        ]:
            await self.async_cancel_timer(timer_id)

    @override
    async def async_add_time(self, timer_id: str, duration: timedelta) -> None:
        """Add (or, with a negative duration, remove) time on a timer."""
        timer = self._get_timer(timer_id)
        if timer.status == TimerStatus.ACTIVE and timer.finishes_at is not None:
            now = dt_util.utcnow()
            finishes_at = timer.finishes_at + duration
            if finishes_at <= now:
                self._unschedule(timer_id)
                self._async_timer_finished(timer_id, now)
                return
            timer.finishes_at = finishes_at
            self._schedule(timer)
        elif timer.status == TimerStatus.PAUSED and timer.remaining is not None:
            timer.remaining = max(timedelta(0), timer.remaining + duration)
        else:
            return
        self._notify(TimerListEventType.UPDATED, timer)

    @override
    async def async_remove_timer(self, timer_id: str) -> None:
        """Remove a timer from the list regardless of its status."""
        timer = self._get_timer(timer_id)
        self._unschedule(timer_id)
        del self._timers[timer_id]
        self._notify(TimerListEventType.REMOVED, timer)

    @override
    async def async_clear_finished_timers(self) -> None:
        """Remove all finished and cancelled (archived) timers."""
        for timer_id in [
            timer.timer_id
            for timer in self._timers.values()
            if timer.status in _FINISHED_STATUSES
        ]:
            timer = self._timers.pop(timer_id)
            self._notify(TimerListEventType.REMOVED, timer)

    def _get_timer(self, timer_id: str) -> TimerItem:
        """Return a timer by id or raise if it does not exist."""
        if (timer := self._timers.get(timer_id)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="timer_not_found",
                translation_placeholders={"timer_id": timer_id},
            )
        return timer

    @callback
    def _schedule(self, timer: TimerItem) -> None:
        """Schedule (or reschedule) the finish callback for a timer."""
        self._unschedule(timer.timer_id)
        assert timer.finishes_at is not None
        self._cancel_callbacks[timer.timer_id] = async_track_point_in_utc_time(
            self.hass,
            partial(self._async_timer_finished, timer.timer_id),
            timer.finishes_at,
        )

    @callback
    def _unschedule(self, timer_id: str) -> None:
        """Cancel a pending finish callback, if any."""
        if cancel := self._cancel_callbacks.pop(timer_id, None):
            cancel()

    @callback
    def _async_timer_finished(self, timer_id: str, now: datetime) -> None:
        """Handle a timer reaching its finish time."""
        self._cancel_callbacks.pop(timer_id, None)
        if (timer := self._timers.get(timer_id)) is None:
            return

        timer.status = TimerStatus.FINISHED
        timer.finishes_at = None
        timer.remaining = None
        timer.finished_at = dt_util.utcnow()
        self._notify(TimerListEventType.FINISHED, timer)

        if timer.finish_action == TimerFinishAction.REMOVE:
            self._timers.pop(timer_id, None)
            self._notify(TimerListEventType.REMOVED, timer)
        elif timer.finish_action == TimerFinishAction.RESTART:
            restarted_at = dt_util.utcnow()
            timer.status = TimerStatus.ACTIVE
            timer.created_at = restarted_at
            timer.finishes_at = restarted_at + timer.duration
            timer.finished_at = None
            self._schedule(timer)
            self._notify(TimerListEventType.STARTED, timer)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel all pending finish callbacks."""
        for cancel in self._cancel_callbacks.values():
            cancel()
        self._cancel_callbacks.clear()


async def create_mock_platform(
    hass: HomeAssistant,
    entities: list[TimerListEntity],
) -> MockConfigEntry:
    """Create a timer_list platform with the specified entities."""

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test timer_list platform via config entry."""
        async_add_entities(entities)

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
