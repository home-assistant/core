"""Offer calendar automation rules."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_EVENT, CONF_OFFSET, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_time_interval,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import DOMAIN, CalendarEntity, CalendarEvent

_LOGGER = logging.getLogger(__name__)

EVENT_START = "start"
EVENT_END = "end"
UPDATE_INTERVAL = datetime.timedelta(minutes=15)

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_EVENT, default=EVENT_START): vol.In({EVENT_START, EVENT_END}),
        vol.Optional(CONF_OFFSET, default=datetime.timedelta(0)): cv.time_period,
    }
)

# mypy: disallow-any-generics


@dataclass
class QueuedCalendarEvent:
    """An event that is queued to be fired in the future."""

    trigger_time: datetime.datetime
    event: CalendarEvent


@dataclass
class Timespan:
    """A time range part of start/end dates, used for considering active events."""

    start: datetime.datetime
    """The start datetime of the interval."""

    end: datetime.datetime
    """The end datetime (exclusive) of the interval."""

    def with_offset(self, offset: datetime.timedelta) -> Timespan:
        """Return a new interval shifted by the specified offset."""
        return Timespan(self.start + offset, self.end + offset)

    def __contains__(self, trigger: datetime.datetime) -> bool:
        """Return true if the trigger time is within the time span."""
        return self.start <= trigger < self.end

    def next_upcoming(
        self, now: datetime.datetime, interval: datetime.timedelta
    ) -> Timespan:
        """Return a subsequent time span following the current time span.

        This effectively gives us a cursor like interface for advancing through
        time using the interval as a hint. The returned span may have a
        different interval than the one specified. For example, time span may
        be longer during a daylight saving time transition, or may extend due to
        drift if the current interval is old. The returned time span is
        adjacent and non-overlapping.
        """
        return Timespan(self.end, max(self.end, now) + interval)

    def __str__(self) -> str:
        """Return a string representing the half open interval time span."""
        return f"[{self.start}, {self.end})"


EventFetcher = Callable[[Timespan], Awaitable[list[CalendarEvent]]]
QueuedEventFetcher = Callable[[Timespan], Awaitable[list[QueuedCalendarEvent]]]


def event_fetcher(hass: HomeAssistant, entity: CalendarEntity) -> EventFetcher:
    """Build an async_get_events wrapper to fetch events during a time span."""

    async def async_get_events(timespan: Timespan) -> list[CalendarEvent]:
        """Return events active in the specified time span."""
        # Expand by one second to make the end time exclusive
        end_time = timespan.end + datetime.timedelta(seconds=1)
        return await entity.async_get_events(hass, timespan.start, end_time)

    return async_get_events


def queued_event_fetcher(
    fetcher: EventFetcher, event_type: str, offset: datetime.timedelta
) -> QueuedEventFetcher:
    """Build a fetcher that produces a schedule of upcoming trigger events."""

    def get_trigger_time(event: CalendarEvent) -> datetime.datetime:
        if event_type == EVENT_START:
            return event.start_datetime_local
        return event.end_datetime_local

    async def async_get_events(timespan: Timespan) -> list[QueuedCalendarEvent]:
        """Get calendar event triggers eligible to fire in the time span."""
        offset_timespan = timespan.with_offset(-1 * offset)
        active_events = await fetcher(offset_timespan)

        # Determine the trigger eligibility of events during this time span.
        # Example: For an EVENT_END trigger the event may start during this
        # time span, but need to be triggered later when the end happens.
        results = []
        for trigger_time, event in zip(
            map(get_trigger_time, active_events), active_events
        ):
            if trigger_time not in offset_timespan:
                continue
            results.append(QueuedCalendarEvent(trigger_time + offset, event))

        _LOGGER.debug(
            "Scan events @ %s%s found %s eligible of %s active",
            offset_timespan,
            f" (offset={offset})" if offset else "",
            len(results),
            len(active_events),
        )
        results.sort(key=lambda x: x.trigger_time)
        return results

    return async_get_events


class CalendarEventListener:
    """Helper class to listen to calendar events.

    This listener will poll every UPDATE_INTERVAL to fetch a set of upcoming
    calendar events in the upcoming window of time, putting them into a queue.
    The queue is drained by scheduling an alarm for the next upcoming event
    trigger time, one event at a time.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        job: HassJob[..., Coroutine[Any, Any, None]],
        trigger_data: dict[str, Any],
        fetcher: QueuedEventFetcher,
    ) -> None:
        """Initialize CalendarEventListener."""
        self._hass = hass
        self._job = job
        self._trigger_data = trigger_data
        self._unsub_event: CALLBACK_TYPE | None = None
        self._unsub_refresh: CALLBACK_TYPE | None = None
        self._fetcher = fetcher
        now = dt_util.now()
        self._timespan = Timespan(now, now + UPDATE_INTERVAL)
        self._events: list[QueuedCalendarEvent] = []

    async def async_attach(self) -> None:
        """Attach a calendar event listener."""
        self._events.extend(await self._fetcher(self._timespan))
        self._unsub_refresh = async_track_time_interval(
            self._hass, self._handle_refresh, UPDATE_INTERVAL
        )
        self._listen_next_calendar_event()

    @callback
    def async_detach(self) -> None:
        """Detach the calendar event listener."""
        self._clear_event_listener()
        if self._unsub_refresh:
            self._unsub_refresh()
        self._unsub_refresh = None

    @callback
    def _listen_next_calendar_event(self) -> None:
        """Set up the calendar event listener."""
        if not self._events:
            return

        _LOGGER.debug(
            "Scheduled next event trigger for %s", self._events[0].trigger_time
        )
        self._unsub_event = async_track_point_in_time(
            self._hass,
            self._handle_calendar_event,
            self._events[0].trigger_time,
        )

    def _clear_event_listener(self) -> None:
        """Reset the event listener."""
        if self._unsub_event:
            self._unsub_event()
        self._unsub_event = None

    async def _handle_calendar_event(self, now: datetime.datetime) -> None:
        """Handle calendar event."""
        _LOGGER.debug("Calendar event @ %s", dt_util.as_local(now))
        self._dispatch_events(now)
        self._clear_event_listener()
        self._listen_next_calendar_event()

    def _dispatch_events(self, now: datetime.datetime) -> None:
        """Dispatch all events that are eligible to fire."""
        while self._events and self._events[0].trigger_time <= now:
            queued_event = self._events.pop(0)
            _LOGGER.debug("Dispatching event: %s", queued_event.event)
            self._hass.async_run_hass_job(
                self._job,
                {
                    "trigger": {
                        **self._trigger_data,
                        "calendar_event": queued_event.event.as_dict(),
                    }
                },
            )

    async def _handle_refresh(self, now_utc: datetime.datetime) -> None:
        """Handle core config update."""
        now = dt_util.as_local(now_utc)
        _LOGGER.debug("Refresh events @ %s", now)
        # Dispatch any eligible events in the boundary case where refresh
        # fires before the calendar event.
        self._dispatch_events(now)
        self._clear_event_listener()
        self._timespan = self._timespan.next_upcoming(now, UPDATE_INTERVAL)
        self._events.extend(await self._fetcher(self._timespan))
        self._listen_next_calendar_event()


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach trigger for the specified calendar."""
    entity_id = config[CONF_ENTITY_ID]
    event_type = config[CONF_EVENT]
    offset = config[CONF_OFFSET]

    component: EntityComponent[CalendarEntity] = hass.data[DOMAIN]
    if not (entity := component.get_entity(entity_id)) or not isinstance(
        entity, CalendarEntity
    ):
        raise HomeAssistantError(
            f"Entity does not exist {entity_id} or is not a calendar entity"
        )

    trigger_data = {
        **trigger_info["trigger_data"],
        "platform": DOMAIN,
        "event": event_type,
        "offset": offset,
    }
    listener = CalendarEventListener(
        hass,
        HassJob(action),
        trigger_data,
        queued_event_fetcher(event_fetcher(hass, entity), event_type, offset),
    )
    await listener.async_attach()
    return listener.async_detach
