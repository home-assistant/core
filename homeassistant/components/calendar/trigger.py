"""Offer calendar automation rules."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import datetime
import logging
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_OFFSET,
    CONF_OPTIONS,
    CONF_TARGET,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import move_top_level_schema_fields_to_options
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_time_interval,
)
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import Trigger, TriggerActionRunner, TriggerConfig
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from . import CalendarEntity, CalendarEvent
from .const import DATA_COMPONENT, DOMAIN

_LOGGER = logging.getLogger(__name__)

EVENT_START = "start"
EVENT_END = "end"
UPDATE_INTERVAL = datetime.timedelta(minutes=15)

CONF_OFFSET_TYPE = "offset_type"
OFFSET_TYPE_BEFORE = "before"
OFFSET_TYPE_AFTER = "after"


_SINGLE_ENTITY_EVENT_OPTIONS_SCHEMA = {
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_EVENT, default=EVENT_START): vol.In({EVENT_START, EVENT_END}),
    vol.Optional(CONF_OFFSET, default=datetime.timedelta(0)): cv.time_period,
}

_SINGLE_ENTITY_EVENT_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): _SINGLE_ENTITY_EVENT_OPTIONS_SCHEMA,
    },
)

_EVENT_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS, default={}): {
            vol.Required(CONF_OFFSET, default=datetime.timedelta(0)): cv.time_period,
            vol.Required(CONF_OFFSET_TYPE, default=OFFSET_TYPE_BEFORE): vol.In(
                {OFFSET_TYPE_BEFORE, OFFSET_TYPE_AFTER}
            ),
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)

# mypy: disallow-any-generics


@dataclass
class QueuedCalendarEvent:
    """An event that is queued to be fired in the future."""

    trigger_time: datetime.datetime
    event: CalendarEvent
    entity_id: str


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


type EventFetcher = Callable[[Timespan], Awaitable[list[tuple[str, CalendarEvent]]]]
type QueuedEventFetcher = Callable[[Timespan], Awaitable[list[QueuedCalendarEvent]]]


def get_entity(hass: HomeAssistant, entity_id: str) -> CalendarEntity:
    """Get the calendar entity for the provided entity_id."""
    component: EntityComponent[CalendarEntity] = hass.data[DATA_COMPONENT]
    if not (entity := component.get_entity(entity_id)) or not isinstance(
        entity, CalendarEntity
    ):
        raise HomeAssistantError(
            f"Entity does not exist {entity_id} or is not a calendar entity"
        )
    return entity


def event_fetcher(hass: HomeAssistant, entity_ids: set[str]) -> EventFetcher:
    """Build an async_get_events wrapper to fetch events during a time span."""

    async def async_get_events(timespan: Timespan) -> list[tuple[str, CalendarEvent]]:
        """Return events active in the specified time span."""
        # Expand by one second to make the end time exclusive
        end_time = timespan.end + datetime.timedelta(seconds=1)

        events: list[tuple[str, CalendarEvent]] = []
        for entity_id in entity_ids:
            entity = get_entity(hass, entity_id)
            events.extend(
                (entity_id, event)
                for event in await entity.async_get_events(
                    hass, timespan.start, end_time
                )
            )
        return events

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
        for entity_id, event in active_events:
            trigger_time = get_trigger_time(event)
            if trigger_time not in offset_timespan:
                continue
            results.append(QueuedCalendarEvent(trigger_time + offset, event, entity_id))

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
        action_runner: TriggerActionRunner,
        trigger_payload: dict[str, Any],
        fetcher: QueuedEventFetcher,
    ) -> None:
        """Initialize CalendarEventListener."""
        self._hass = hass
        self._action_runner = action_runner
        self._trigger_payload = trigger_payload
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
            payload = {
                **self._trigger_payload,
                ATTR_ENTITY_ID: queued_event.entity_id,
                "calendar_event": queued_event.event.as_dict(),
            }
            self._action_runner(payload, "calendar event state change")

    async def _handle_refresh(self, now_utc: datetime.datetime) -> None:
        """Handle core config update."""
        now = dt_util.as_local(now_utc)
        _LOGGER.debug("Refresh events @ %s", now)
        # Dispatch any eligible events in the boundary case where refresh
        # fires before the calendar event.
        self._dispatch_events(now)
        self._clear_event_listener()
        self._timespan = self._timespan.next_upcoming(now, UPDATE_INTERVAL)
        try:
            self._events.extend(await self._fetcher(self._timespan))
        except HomeAssistantError as ex:
            _LOGGER.error("Calendar trigger failed to fetch events: %s", ex)
        self._listen_next_calendar_event()


class TargetCalendarEventListener(TargetEntityChangeTracker):
    """Helper class to listen to calendar events for target entity changes."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        event_type: str,
        offset: datetime.timedelta,
        run_action: TriggerActionRunner,
    ) -> None:
        """Initialize the state change tracker."""

        def entity_filter(entities: set[str]) -> set[str]:
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        super().__init__(hass, target_selection, entity_filter)
        self._event_type = event_type
        self._offset = offset
        self._run_action = run_action
        self._trigger_data = {
            "event": event_type,
            "offset": offset,
        }

        self._pending_listener_task: asyncio.Task[None] | None = None
        self._calendar_event_listener: CalendarEventListener | None = None

    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Restart the listeners when the list of entities of the tracked targets is updated."""
        if self._pending_listener_task:
            self._pending_listener_task.cancel()
        self._pending_listener_task = self._hass.async_create_task(
            self._start_listening(tracked_entities)
        )

    async def _start_listening(self, tracked_entities: set[str]) -> None:
        """Start listening for calendar events."""
        _LOGGER.debug("Tracking events for calendars: %s", tracked_entities)
        if self._calendar_event_listener:
            self._calendar_event_listener.async_detach()
        self._calendar_event_listener = CalendarEventListener(
            self._hass,
            self._run_action,
            self._trigger_data,
            queued_event_fetcher(
                event_fetcher(self._hass, tracked_entities),
                self._event_type,
                self._offset,
            ),
        )
        await self._calendar_event_listener.async_attach()

    def _unsubscribe(self) -> None:
        """Unsubscribe from all events."""
        super()._unsubscribe()
        if self._pending_listener_task:
            self._pending_listener_task.cancel()
            self._pending_listener_task = None
        if self._calendar_event_listener:
            self._calendar_event_listener.async_detach()
            self._calendar_event_listener = None


class SingleEntityEventTrigger(Trigger):
    """Legacy single calendar entity event trigger."""

    _options: dict[str, Any]

    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _SINGLE_ENTITY_EVENT_OPTIONS_SCHEMA
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _SINGLE_ENTITY_EVENT_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)

        if TYPE_CHECKING:
            assert config.options is not None
        self._options = config.options

    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""

        entity_id = self._options[CONF_ENTITY_ID]
        event_type = self._options[CONF_EVENT]
        offset = self._options[CONF_OFFSET]

        # Validate the entity id is valid
        get_entity(self._hass, entity_id)

        trigger_data = {
            "event": event_type,
            "offset": offset,
        }
        listener = CalendarEventListener(
            self._hass,
            run_action,
            trigger_data,
            queued_event_fetcher(
                event_fetcher(self._hass, {entity_id}), event_type, offset
            ),
        )
        await listener.async_attach()
        return listener.async_detach


class EventTrigger(Trigger):
    """Calendar event trigger."""

    _options: dict[str, Any]
    _event_type: str

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _EVENT_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)

        if TYPE_CHECKING:
            assert config.target is not None
            assert config.options is not None
        self._target = config.target
        self._options = config.options

    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""

        offset = self._options[CONF_OFFSET]
        offset_type = self._options[CONF_OFFSET_TYPE]

        if offset_type == OFFSET_TYPE_BEFORE:
            offset = -offset

        target_selection = TargetSelection(self._target)
        if not target_selection.has_any_target:
            raise HomeAssistantError(f"No target defined in {self._target}")
        listener = TargetCalendarEventListener(
            self._hass, target_selection, self._event_type, offset, run_action
        )
        return listener.async_setup()


class EventStartedTrigger(EventTrigger):
    """Calendar event started trigger."""

    _event_type = EVENT_START


class EventEndedTrigger(EventTrigger):
    """Calendar event ended trigger."""

    _event_type = EVENT_END


TRIGGERS: dict[str, type[Trigger]] = {
    "_": SingleEntityEventTrigger,
    "event_started": EventStartedTrigger,
    "event_ended": EventEndedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for calendars."""
    return TRIGGERS
