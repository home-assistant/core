"""Timer list that keeps its timers in memory."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
import math
from typing import Any, override

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util, ulid as ulid_util

from .const import DOMAIN, TimerListEntityFeature, TimerListEventType, TimerStatus
from .entity import TimerItem, TimerListEntity

_ARCHIVE_EVENTS = {
    TimerStatus.FINISHED: TimerListEventType.FINISHED,
    TimerStatus.CANCELLED: TimerListEventType.CANCELLED,
}
MAX_ARCHIVED_TIMERS = 10


class InMemoryTimerListEntity(TimerListEntity):
    """A timer list that keeps its timers in memory.

    Timers are lost when the entity is removed, for example on a config entry
    reload or a restart. Finished and cancelled timers are archived, keeping
    the ``MAX_ARCHIVED_TIMERS`` most recent. Subclasses provide the entity's
    identity: unique id, name and device.
    """

    _attr_supported_features = (
        TimerListEntityFeature.CREATE_TIMER
        | TimerListEntityFeature.PAUSE_TIMER
        | TimerListEntityFeature.CANCEL_TIMER
        | TimerListEntityFeature.FINISH_TIMER
        | TimerListEntityFeature.ADD_TIME
        | TimerListEntityFeature.REMOVE_TIMER
    )

    def __init__(self) -> None:
        """Initialize the timer list."""
        super().__init__()
        self._timers: dict[str, TimerItem] = {}
        self._cancel_callbacks: dict[str, CALLBACK_TYPE] = {}

    @property
    @override
    def timers(self) -> list[TimerItem]:
        """Return the timers in the list."""
        return list(self._timers.values())

    def _get_timer(self, timer_id: str) -> TimerItem:
        """Return a timer by id or raise if it does not exist."""
        if (timer := self._timers.get(timer_id)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="timer_not_found",
                translation_placeholders={"timer_id": timer_id},
            )
        return timer

    @override
    async def async_create_timer(self, *, name: str | None, duration: timedelta) -> str:
        """Create a new timer, returning its id."""
        now = dt_util.utcnow()
        timer = TimerItem(
            timer_id=ulid_util.ulid_now(),
            name=name,
            status=TimerStatus.ACTIVE,
            created_duration=duration,
            created_at=now,
        )
        self._timers[timer.timer_id] = timer
        self._schedule(timer, now + duration)
        self._notify(TimerListEventType.CREATED, timer)
        return timer.timer_id

    @override
    async def async_pause_timer(self, timer_id: str) -> None:
        """Pause an active timer."""
        timer = self._get_timer(timer_id)
        if timer.status != TimerStatus.ACTIVE:
            return
        timer.paused_remaining = timer.remaining_at(dt_util.utcnow())
        timer.finishes_at = None
        timer.status = TimerStatus.PAUSED
        self._unschedule(timer_id)
        self._notify(TimerListEventType.PAUSED, timer)

    @override
    async def async_unpause_timer(self, timer_id: str) -> None:
        """Resume a paused timer."""
        timer = self._get_timer(timer_id)
        if timer.status != TimerStatus.PAUSED or timer.paused_remaining is None:
            return
        self._schedule(timer, dt_util.utcnow() + timer.paused_remaining)
        timer.paused_remaining = None
        timer.status = TimerStatus.ACTIVE
        self._notify(TimerListEventType.UNPAUSED, timer)

    @override
    async def async_cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer, archiving it as ``cancelled``."""
        timer = self._get_timer(timer_id)
        if timer.status in _ARCHIVE_EVENTS:
            return
        self._archive(timer, TimerStatus.CANCELLED)

    @override
    async def async_finish_timer(self, timer_id: str) -> None:
        """Finish a timer early, archiving it as ``finished``."""
        timer = self._get_timer(timer_id)
        if timer.status in _ARCHIVE_EVENTS:
            return
        self._archive(timer, TimerStatus.FINISHED)

    @override
    async def async_add_time(self, timer_id: str, duration: timedelta) -> None:
        """Add (or, with a negative duration, subtract) time on a timer."""
        timer = self._get_timer(timer_id)
        if timer.status not in (TimerStatus.ACTIVE, TimerStatus.PAUSED) or not duration:
            return
        now = dt_util.utcnow()
        remaining = timer.remaining_at(now) + duration
        if remaining <= timedelta(0):
            self._archive(timer, TimerStatus.FINISHED)
            return
        if timer.status == TimerStatus.PAUSED:
            timer.paused_remaining = remaining
        else:
            self._schedule(timer, now + remaining)
        # Round up to whole seconds: the timer's sub-second age would otherwise
        # make the total fall short of what was asked for.
        timer.total_duration = max(
            timer.total_duration,
            timedelta(seconds=math.ceil(remaining.total_seconds())),
        )
        self._notify(TimerListEventType.TIME_CHANGED, timer, delta=duration)

    @override
    async def async_remove_timer(self, timer_id: str) -> None:
        """Remove a timer from the list regardless of its status."""
        timer = self._get_timer(timer_id)
        self._unschedule(timer_id)
        del self._timers[timer_id]
        self._notify(TimerListEventType.REMOVED, timer)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel all pending finish callbacks."""
        for cancel in self._cancel_callbacks.values():
            cancel()
        self._cancel_callbacks.clear()

    @callback
    def _schedule(self, timer: TimerItem, finishes_at: datetime) -> None:
        """Set when an active timer finishes and schedule its finish callback."""
        self._unschedule(timer.timer_id)
        timer.finishes_at = finishes_at
        self._cancel_callbacks[timer.timer_id] = async_track_point_in_utc_time(
            self.hass, partial(self._async_timer_finished, timer.timer_id), finishes_at
        )

    @callback
    def _unschedule(self, timer_id: str) -> None:
        """Cancel the pending finish callback of a timer, if any."""
        if cancel := self._cancel_callbacks.pop(timer_id, None):
            cancel()

    @callback
    def _async_timer_finished(self, timer_id: str, now: datetime) -> None:
        """Archive a timer that reached its finish time."""
        del self._cancel_callbacks[timer_id]
        self._archive(self._timers[timer_id], TimerStatus.FINISHED)

    @callback
    def _archive(self, timer: TimerItem, status: TimerStatus) -> None:
        """Move a timer to a terminal status and notify subscribers."""
        self._unschedule(timer.timer_id)
        timer.status = status
        timer.finishes_at = None
        timer.paused_remaining = None
        timer.ended_at = dt_util.utcnow()
        self._notify(_ARCHIVE_EVENTS[status], timer)
        self._evict_archived()

    @callback
    def _evict_archived(self) -> None:
        """Remove the oldest archived timers beyond ``MAX_ARCHIVED_TIMERS``."""
        archived = sorted(
            (timer.ended_at, timer.timer_id)
            for timer in self._timers.values()
            if timer.ended_at is not None
        )
        for _, timer_id in archived[: max(0, len(archived) - MAX_ARCHIVED_TIMERS)]:
            self._notify(TimerListEventType.REMOVED, self._timers.pop(timer_id))


def _timer_as_stored(timer: TimerItem) -> dict[str, Any]:
    """Return a timer as JSON-serializable data to restore it from."""
    return {
        "timer_id": timer.timer_id,
        "name": timer.name,
        "status": timer.status.value,
        "created_duration": timer.created_duration.total_seconds(),
        "created_at": timer.created_at.isoformat(),
        "total_duration": timer.total_duration.total_seconds(),
        "finishes_at": timer.finishes_at.isoformat() if timer.finishes_at else None,
        "paused_remaining": (
            timer.paused_remaining.total_seconds()
            if timer.paused_remaining is not None
            else None
        ),
        "ended_at": timer.ended_at.isoformat() if timer.ended_at else None,
    }


def _timer_from_stored(data: dict[str, Any]) -> TimerItem:
    """Return a timer from data stored by ``_timer_as_stored``."""

    def _datetime(value: str | None) -> datetime | None:
        if value is None:
            return None
        if (parsed := dt_util.parse_datetime(value)) is None:
            raise ValueError(f"invalid datetime: {value}")
        return parsed

    def _seconds(value: float | None) -> timedelta | None:
        return None if value is None else timedelta(seconds=value)

    created_at = _datetime(data["created_at"])
    created_duration = _seconds(data["created_duration"])
    if created_at is None or created_duration is None:
        raise ValueError("timer without creation time or duration")
    return TimerItem(
        timer_id=data["timer_id"],
        name=data["name"],
        status=TimerStatus(data["status"]),
        created_duration=created_duration,
        created_at=created_at,
        total_duration=_seconds(data["total_duration"]) or timedelta(0),
        finishes_at=_datetime(data["finishes_at"]),
        paused_remaining=_seconds(data["paused_remaining"]),
        ended_at=_datetime(data["ended_at"]),
    )


@dataclass
class TimerListExtraStoredData(ExtraStoredData):
    """Timers of a timer list, stored to restore them."""

    timers: list[dict[str, Any]]

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return the stored timers."""
        return {"timers": self.timers}


class RestoreTimerListEntity(InMemoryTimerListEntity, RestoreEntity):
    """An in-memory timer list that keeps its timers across restarts and reloads.

    Active timers that should have finished while Home Assistant was not
    running are archived as ``finished`` when they are restored, at the time
    they should have finished. No event is emitted for them: acting on a
    timer long after it ran out, for example by ringing, is more surprising
    than not acting at all.
    """

    def __init__(self) -> None:
        """Initialize the timer list."""
        super().__init__()
        self._restored_running: dict[str, str | None] = {}
        """Timers that were active or paused when the list was stored, by id,
        with their names; whether they are still running or not."""

    @property
    @override
    def extra_restore_state_data(self) -> TimerListExtraStoredData:
        """Return the timers to restore."""
        return TimerListExtraStoredData(
            [_timer_as_stored(timer) for timer in self._timers.values()]
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the timers of the previous run."""
        await super().async_added_to_hass()
        if (extra_data := await self.async_get_last_extra_data()) is None:
            return
        now = dt_util.utcnow()
        for data in extra_data.as_dict().get("timers", []):
            try:
                timer = _timer_from_stored(data)
            except KeyError, TypeError, ValueError:
                continue
            if timer.timer_id in self._timers:
                continue
            self._timers[timer.timer_id] = timer
            if timer.status not in (TimerStatus.ACTIVE, TimerStatus.PAUSED):
                continue
            self._restored_running[timer.timer_id] = timer.name
            if timer.status == TimerStatus.PAUSED:
                continue
            if timer.finishes_at is not None and timer.finishes_at > now:
                self._schedule(timer, timer.finishes_at)
                continue
            timer.status = TimerStatus.FINISHED
            timer.ended_at = timer.finishes_at or now
            timer.finishes_at = None
        self._evict_archived()
