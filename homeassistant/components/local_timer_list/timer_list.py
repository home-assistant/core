"""Local timer list platform."""

from datetime import datetime, timedelta
from functools import partial
from typing import override

from homeassistant.components.timer_list import (
    DOMAIN as TIMER_LIST_DOMAIN,
    TimerItem,
    TimerListEntity,
    TimerListEntityFeature,
    TimerListEventType,
    TimerStatus,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util, ulid as ulid_util

from .const import CONF_TIMER_LIST_NAME

_FINISHED_STATUSES = (TimerStatus.FINISHED, TimerStatus.CANCELLED)
MAX_ARCHIVED_TIMERS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the local timer list entity from a config entry."""
    async_add_entities([LocalTimerListEntity(config_entry)])


class LocalTimerListEntity(TimerListEntity):
    """A local, in-memory timer list."""

    _attr_supported_features = (
        TimerListEntityFeature.START_TIMER
        | TimerListEntityFeature.PAUSE_TIMER
        | TimerListEntityFeature.CANCEL_TIMER
        | TimerListEntityFeature.ADD_TIME
    )

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the timer list."""
        super().__init__()
        self._attr_name = config_entry.data[CONF_TIMER_LIST_NAME]
        self._attr_unique_id = config_entry.entry_id
        self._timers: dict[str, TimerItem] = {}
        self._cancel_callbacks: dict[str, CALLBACK_TYPE] = {}

    @property
    @override
    def timers(self) -> list[TimerItem]:
        """Return the timers in the list."""
        return list(self._timers.values())

    @override
    async def async_start_timer(self, *, name: str | None, duration: timedelta) -> str:
        """Create and start a new timer, returning its id."""
        now = dt_util.utcnow()
        timer_id = ulid_util.ulid_now()
        timer = TimerItem(
            timer_id=timer_id,
            name=name,
            status=TimerStatus.ACTIVE,
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
        """Cancel a timer, archiving it in the ``cancelled`` state."""
        timer = self._get_timer(timer_id)
        self._unschedule(timer_id)
        timer.status = TimerStatus.CANCELLED
        timer.finishes_at = None
        timer.remaining = None
        timer.finished_at = dt_util.utcnow()
        self._notify(TimerListEventType.CANCELLED, timer)
        self._enforce_archive_limit()

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
                translation_domain=TIMER_LIST_DOMAIN,
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
        """Handle a timer reaching its finish time, archiving it."""
        self._cancel_callbacks.pop(timer_id, None)
        if (timer := self._timers.get(timer_id)) is None:
            return

        timer.status = TimerStatus.FINISHED
        timer.finishes_at = None
        timer.remaining = None
        timer.finished_at = dt_util.utcnow()
        self._notify(TimerListEventType.FINISHED, timer)
        self._enforce_archive_limit()

    @callback
    def _enforce_archive_limit(self) -> None:
        """Evict the oldest archived timers beyond ``MAX_ARCHIVED_TIMERS``."""
        archived = sorted(
            (
                timer
                for timer in self._timers.values()
                if timer.status in _FINISHED_STATUSES
            ),
            key=lambda timer: timer.finished_at or dt_util.utcnow(),
        )
        excess = len(archived) - MAX_ARCHIVED_TIMERS
        if excess <= 0:
            return
        for timer in archived[:excess]:
            del self._timers[timer.timer_id]
            self._notify(TimerListEventType.REMOVED, timer)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel all pending finish callbacks."""
        for cancel in self._cancel_callbacks.values():
            cancel()
        self._cancel_callbacks.clear()
