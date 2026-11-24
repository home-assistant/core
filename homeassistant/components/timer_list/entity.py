"""Entities for timer lists."""

from collections.abc import Callable
import copy
import dataclasses
from datetime import datetime, timedelta
from typing import Any, final, override

from homeassistant.const import ATTR_NAME
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_CREATED_AT,
    ATTR_CREATED_DURATION,
    ATTR_ENDED_AT,
    ATTR_FINISHES_AT,
    ATTR_PAUSED_REMAINING,
    ATTR_REMAINING,
    ATTR_STATUS,
    ATTR_TIMER_ID,
    ATTR_TOTAL_DURATION,
    TimerListEventType,
    TimerStatus,
)


@dataclasses.dataclass
class TimerItem:
    """A single timer within a timer list."""

    timer_id: str
    """Generated unique id of the timer."""

    name: str | None
    """Optional user-provided name."""

    status: TimerStatus
    """Current status of the timer."""

    created_duration: timedelta
    """Duration the timer was created with. Never changes.

    This is what voice commands disambiguate on, so "the 5 minute timer" keeps
    referring to the same timer after time is added to it. For how long the
    timer currently runs for, use ``total_duration``.
    """

    created_at: datetime
    """When the timer was created, in UTC. Never changes."""

    total_duration: timedelta = timedelta(0)
    """Longest the timer has ever had left to run, i.e. the denominator for a
    progress display. Raised (never lowered) as time is added, and never less
    than ``created_duration``."""

    finishes_at: datetime | None = None
    """Absolute time the timer will finish, in UTC. ``None`` unless active."""

    paused_remaining: timedelta | None = None
    """Time left frozen at the moment of pausing. ``None`` unless paused."""

    ended_at: datetime | None = None
    """When the timer finished or was cancelled, in UTC. ``None`` until then."""

    def __post_init__(self) -> None:
        """Start the progress total at the created duration."""
        self.total_duration = max(self.total_duration, self.created_duration)

    def remaining_at(self, now: datetime) -> timedelta:
        """Return the time left on the timer relative to ``now``."""
        if self.status == TimerStatus.ACTIVE and self.finishes_at is not None:
            return max(timedelta(0), self.finishes_at - now)
        if self.status == TimerStatus.PAUSED and self.paused_remaining is not None:
            return self.paused_remaining
        return timedelta(0)

    def as_dict(self, now: datetime) -> dict[str, Any]:
        """Serialize the timer at the supplied time."""
        return {
            ATTR_TIMER_ID: self.timer_id,
            ATTR_NAME: self.name,
            ATTR_STATUS: self.status.value,
            ATTR_CREATED_DURATION: self.created_duration.total_seconds(),
            ATTR_TOTAL_DURATION: self.total_duration.total_seconds(),
            ATTR_CREATED_AT: self.created_at.isoformat(),
            ATTR_FINISHES_AT: self.finishes_at.isoformat()
            if self.finishes_at
            else None,
            ATTR_PAUSED_REMAINING: (
                self.paused_remaining.total_seconds()
                if self.paused_remaining is not None
                else None
            ),
            ATTR_ENDED_AT: self.ended_at.isoformat() if self.ended_at else None,
            ATTR_REMAINING: self.remaining_at(now).total_seconds(),
        }


@dataclasses.dataclass(frozen=True)
class TimerListEvent:
    """A change to a timer, pushed to subscribers and triggers."""

    event_type: TimerListEventType
    item: TimerItem

    delta: timedelta | None = None
    """Signed amount of time added, for ``TIME_CHANGED``. ``None`` otherwise."""


class TimerListEntity(Entity):
    """An entity that holds a list of independent countdown timers.

    This base class only provides the event/listener plumbing shared by the
    websocket API and triggers. Concrete implementations are responsible for
    storing timers and scheduling their completion.

    Subclasses own the timers, wherever they live: in memory, on a device, or
    behind a remote API. A subclass always keeps a local copy of them, because
    ``timers`` and ``state`` are read synchronously and cannot wait on a remote.

    Every action method takes a timer id and must, unless noted otherwise:

    - raise ``ServiceValidationError`` with this integration's
      ``timer_not_found`` translation key for an unknown id, so every backend
      reports one identically;
    - do nothing at all if the timer is already ``finished`` or ``cancelled``,
      or is otherwise in a state the action does not apply to, rather than
      raising or emitting an event;
    - emit exactly one event via ``_notify`` when it does change something.

    Voice intents call these methods directly and do not check
    ``supported_features``, so an action may be invoked on an entity that does
    not advertise it.
    """

    _attr_should_poll = False

    def __init__(self) -> None:
        """Initialize the timer list."""
        self._update_listeners: list[Callable[[TimerListEvent], None]] = []

    @property
    @override
    def state(self) -> int:
        """Return the number of active timers."""
        return sum(timer.status == TimerStatus.ACTIVE for timer in self.timers)

    @property
    def timers(self) -> list[TimerItem]:
        """Return the timers in the list.

        Includes archived (``finished`` and ``cancelled``) timers, which the
        websocket API and ``get_timers`` report. Voice commands only ever
        consider active and paused timers.
        """
        raise NotImplementedError

    async def async_create_timer(self, *, name: str | None, duration: timedelta) -> str:
        """Create a new timer, returning its id.

        The timer starts counting down immediately; there is no created-but-not
        -running state. Emits ``CREATED``.
        """
        raise NotImplementedError

    async def async_pause_timer(self, timer_id: str) -> None:
        """Pause an active timer, emitting ``PAUSED``.

        Does nothing if the timer is not currently ``active``. The time left
        must be frozen in ``paused_remaining`` so it survives the pause.
        """
        raise NotImplementedError

    async def async_unpause_timer(self, timer_id: str) -> None:
        """Resume a paused timer, emitting ``UNPAUSED``.

        Does nothing if the timer is not currently ``paused``.
        """
        raise NotImplementedError

    async def async_cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer without finishing it, emitting ``CANCELLED``.

        The timer stays in the list as ``cancelled`` with ``ended_at`` set. No
        ``FINISHED`` event is emitted, so satellites stay silent.
        """
        raise NotImplementedError

    async def async_finish_timer(self, timer_id: str) -> None:
        """Finish a timer early, as if its remaining time had elapsed.

        Emits ``FINISHED``, so satellites ring, and leaves the timer in the
        list as ``finished`` with ``ended_at`` set. Applies to paused timers
        too. ``FINISHED`` therefore does not imply the full duration elapsed.
        """
        raise NotImplementedError

    async def async_add_time(self, timer_id: str, duration: timedelta) -> None:
        """Add (or, with a negative duration, subtract) time on a timer.

        Emits ``TIME_CHANGED`` carrying ``duration`` as the event's signed
        ``delta``. ``created_duration`` must not change, and ``total_duration``
        must be raised so it stays at least the new remaining time. Subtracting
        more than is left finishes the timer instead, emitting ``FINISHED``,
        whether it was active or paused. A zero ``duration`` changes nothing
        and emits no event.
        """
        raise NotImplementedError

    async def async_remove_timer(self, timer_id: str) -> None:
        """Remove a timer from the list regardless of its status.

        Emits ``REMOVED``. Implementations may also emit it unprompted when
        evicting old archived timers, so subscribers must tolerate it for a
        timer they did not ask to remove.
        """
        raise NotImplementedError

    @final
    @callback
    def async_subscribe_updates(
        self, listener: Callable[[TimerListEvent], None]
    ) -> CALLBACK_TYPE:
        """Subscribe to timer change events.

        Only future changes are pushed; the current set of timers is not
        replayed on subscribe.
        """
        self._update_listeners.append(listener)

        @callback
        def unsubscribe() -> None:
            self._update_listeners.remove(listener)

        return unsubscribe

    @final
    @callback
    def _notify(
        self,
        event_type: TimerListEventType,
        timer: TimerItem,
        delta: timedelta | None = None,
    ) -> None:
        """Push a change event to subscribers and write entity state."""
        event = TimerListEvent(
            event_type=event_type, item=copy.copy(timer), delta=delta
        )
        self.async_write_ha_state()
        for listener in list(self._update_listeners):
            listener(event)
