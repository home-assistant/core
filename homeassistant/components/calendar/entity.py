"""Base entity for the Calendar platform."""

from collections import defaultdict
from collections.abc import Callable, Iterable
import dataclasses
import datetime as dt
import logging
from typing import Any, final, override

import probatio

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import (
    DOMAIN,
    EVENT_LISTENER_DEBOUNCE_COOLDOWN,
    EVENT_RRULE,
    EVENT_SUMMARY,
    CalendarEntityStateAttribute,
    CalendarEventStatus,
)
from .helper import (
    MIN_EVENT_DURATION,
    as_local_timezone,
    event_dict_factory,
    get_datetime_local,
    has_min_duration,
    has_same_type,
    has_timezone,
    validate_rrule,
)

_LOGGER = logging.getLogger(__package__)


# Validation for the CalendarEvent dataclass
CALENDAR_EVENT_SCHEMA = probatio.Schema(
    probatio.All(
        {
            probatio.Required("start"): probatio.Any(cv.date, cv.datetime),
            probatio.Required("end"): probatio.Any(cv.date, cv.datetime),
            probatio.Required(EVENT_SUMMARY): cv.string,
            probatio.Optional(EVENT_RRULE): validate_rrule,
        },
        has_same_type("start", "end"),
        has_timezone("start", "end"),
        as_local_timezone("start", "end"),
        has_min_duration("start", "end", MIN_EVENT_DURATION),
    ),
    extra=probatio.ALLOW_EXTRA,
)


@dataclasses.dataclass
class CalendarEvent:
    """An event on a calendar."""

    start: dt.date | dt.datetime
    end: dt.date | dt.datetime
    summary: str
    description: str | None = None
    location: str | None = None

    uid: str | None = None
    recurrence_id: str | None = None
    rrule: str | None = None
    status: CalendarEventStatus | None = None

    @property
    def start_datetime_local(self) -> dt.datetime:
        """Return event start time as a local datetime."""
        return get_datetime_local(self.start)

    @property
    def end_datetime_local(self) -> dt.datetime:
        """Return event end time as a local datetime."""
        return get_datetime_local(self.end)

    @property
    def all_day(self) -> bool:
        """Return true if the event is an all day event."""
        return not isinstance(self.start, dt.datetime)

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the event."""
        return {
            **dataclasses.asdict(self, dict_factory=event_dict_factory),
            "all_day": self.all_day,
        }

    def __post_init__(self) -> None:
        """Perform validation on the CalendarEvent."""

        def skip_none(obj: Iterable[tuple[str, Any]]) -> dict[str, str]:
            return {k: v for k, v in obj if v is not None}

        try:
            CALENDAR_EVENT_SCHEMA(dataclasses.asdict(self, dict_factory=skip_none))
        except probatio.Invalid as err:
            raise HomeAssistantError(
                f"Failed to validate CalendarEvent: {err}"
            ) from err

        # It is common to set a start an end date to be the same thing for
        # an all day event, but that is not a valid duration. Fix to have a
        # duration of one day.
        if (
            not isinstance(self.start, dt.datetime)
            and not isinstance(self.end, dt.datetime)
            and self.start == self.end
        ):
            self.end = self.start + dt.timedelta(days=1)


class CalendarEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes calendar entities."""

    initial_color: str | None = None


class CalendarEntity(Entity):
    """Base class for calendar event entities."""

    entity_description: CalendarEntityDescription

    _entity_component_unrecorded_attributes = frozenset(
        {CalendarEntityStateAttribute.DESCRIPTION}
    )

    _alarm_unsubs: list[CALLBACK_TYPE] | None = None
    _event_listeners: (
        list[
            tuple[
                dt.datetime,
                dt.datetime,
                Callable[[list[JsonValueType] | None], None],
            ]
        ]
        | None
    ) = None
    _event_listener_debouncer: Debouncer[None] | None = None

    _attr_initial_color: str | None

    @property
    def initial_color(self) -> str | None:
        """Return the initial color for the calendar entity."""
        if hasattr(self, "_attr_initial_color"):
            return self._attr_initial_color
        if hasattr(self, "entity_description"):
            return self.entity_description.initial_color
        return None

    @override
    def get_initial_entity_options(self) -> er.EntityOptionsType | None:
        """Return initial entity options."""
        if self.initial_color is None:
            return None

        # Validate that it's a valid hex color string with # prefix
        try:
            validated_color = cv.color_hex(self.initial_color)
        except probatio.Invalid:
            return None

        return {DOMAIN: {"color": validated_color}}

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        raise NotImplementedError

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the entity state attributes."""
        if (event := self.event) is None:
            return None

        return {
            CalendarEntityStateAttribute.MESSAGE: event.summary,
            CalendarEntityStateAttribute.ALL_DAY: event.all_day,
            CalendarEntityStateAttribute.START_TIME: event.start_datetime_local.strftime(
                DATE_STR_FORMAT
            ),
            CalendarEntityStateAttribute.END_TIME: event.end_datetime_local.strftime(
                DATE_STR_FORMAT
            ),
            CalendarEntityStateAttribute.LOCATION: event.location or "",
            CalendarEntityStateAttribute.DESCRIPTION: event.description or "",
        }

    @final
    @property
    @override
    def state(self) -> str:
        """Return the state of the calendar event."""
        if (event := self.event) is None:
            return STATE_OFF

        now = dt_util.now()

        if event.start_datetime_local <= now < event.end_datetime_local:
            return STATE_ON

        return STATE_OFF

    @callback
    @override
    def _async_write_ha_state(self) -> None:
        """Write the state to the state machine.

        This sets up listeners to handle state transitions for start or end of
        the current or upcoming event.
        """
        super()._async_write_ha_state()

        # Notify websocket subscribers of event changes (debounced)
        if self._event_listeners and self._event_listener_debouncer:
            self._event_listener_debouncer.async_schedule_call()
        if self._alarm_unsubs is None:
            self._alarm_unsubs = []
        _LOGGER.debug(
            "Clearing %s alarms (%s)", self.entity_id, len(self._alarm_unsubs)
        )
        for unsub in self._alarm_unsubs:
            unsub()
        self._alarm_unsubs.clear()

        now = dt_util.now()
        event = self.event
        if event is None or now >= event.end_datetime_local:
            _LOGGER.debug("No alarms needed for %s (event=%s)", self.entity_id, event)
            return

        @callback
        def update(_: dt.datetime) -> None:
            """Update state and reschedule next alarms."""
            _LOGGER.debug("Running %s update", self.entity_id)
            self.async_write_ha_state()

        if now < event.start_datetime_local:
            self._alarm_unsubs.append(
                async_track_point_in_time(
                    self.hass,
                    update,
                    event.start_datetime_local,
                )
            )
        self._alarm_unsubs.append(
            async_track_point_in_time(self.hass, update, event.end_datetime_local)
        )
        _LOGGER.debug(
            "Scheduled %d updates for %s (%s, %s)",
            len(self._alarm_unsubs),
            self.entity_id,
            event.start_datetime_local,
            event.end_datetime_local,
        )

    @callback
    def _async_cancel_event_listener_debouncer(self) -> None:
        """Cancel and clear the event listener debouncer."""
        if self._event_listener_debouncer:
            self._event_listener_debouncer.async_cancel()
            self._event_listener_debouncer = None

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        To be extended by integrations.
        """
        for unsub in self._alarm_unsubs or ():
            unsub()
        self._alarm_unsubs = None
        self._async_cancel_event_listener_debouncer()

    @final
    @callback
    def async_subscribe_events(
        self,
        start_date: dt.datetime,
        end_date: dt.datetime,
        event_listener: Callable[[list[JsonValueType] | None], None],
    ) -> CALLBACK_TYPE:
        """Subscribe to calendar event updates.

        Called by websocket API.
        """
        if self._event_listeners is None:
            self._event_listeners = []

        if self._event_listener_debouncer is None:
            self._event_listener_debouncer = Debouncer(
                self.hass,
                _LOGGER,
                cooldown=EVENT_LISTENER_DEBOUNCE_COOLDOWN,
                immediate=True,
                function=self.async_update_event_listeners,
            )

        listener_data = (start_date, end_date, event_listener)
        self._event_listeners.append(listener_data)

        @callback
        def unsubscribe() -> None:
            if self._event_listeners:
                self._event_listeners.remove(listener_data)
            if not self._event_listeners:
                self._async_cancel_event_listener_debouncer()

        return unsubscribe

    @final
    @callback
    def async_update_event_listeners(self) -> None:
        """Push updated calendar events to all listeners."""
        if not self._event_listeners:
            return

        # Expanding the events is the expensive part, and every dashboard
        # showing the same days asks for the same range, so those listeners
        # are served from a single fetch.
        listeners_by_range: defaultdict[
            tuple[dt.datetime, dt.datetime],
            list[Callable[[list[JsonValueType] | None], None]],
        ] = defaultdict(list)
        for start_date, end_date, listener in self._event_listeners:
            listeners_by_range[(start_date, end_date)].append(listener)

        for (start_date, end_date), listeners in listeners_by_range.items():
            self._async_schedule_listener_update(start_date, end_date, listeners)

    @final
    @callback
    def async_update_single_event_listener(
        self,
        start_date: dt.datetime,
        end_date: dt.datetime,
        listener: Callable[[list[JsonValueType] | None], None],
    ) -> None:
        """Schedule an event fetch and push to a single listener."""
        self._async_schedule_listener_update(start_date, end_date, [listener])

    @callback
    def _async_schedule_listener_update(
        self,
        start_date: dt.datetime,
        end_date: dt.datetime,
        listeners: list[Callable[[list[JsonValueType] | None], None]],
    ) -> None:
        """Schedule an event fetch and push to the given listeners."""
        self.hass.async_create_task(
            self._async_update_listeners(start_date, end_date, listeners)
        )

    async def _async_update_listeners(
        self,
        start_date: dt.datetime,
        end_date: dt.datetime,
        listeners: list[Callable[[list[JsonValueType] | None], None]],
    ) -> None:
        """Fetch events and push them to the listeners of that range."""
        try:
            events = await self.async_get_events(self.hass, start_date, end_date)
        except HomeAssistantError as err:
            _LOGGER.debug(
                "Error fetching calendar events for %s: %s",
                self.entity_id,
                err,
            )
            for listener in listeners:
                listener(None)
            return

        event_list: list[JsonValueType] = [event.as_dict() for event in events]
        for listener in listeners:
            listener(event_list)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: dt.datetime,
        end_date: dt.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        raise NotImplementedError

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a new event to calendar."""
        raise NotImplementedError

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event on the calendar."""
        raise NotImplementedError

    async def async_update_event(
        self,
        uid: str,
        event: dict[str, Any],
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event on the calendar."""
        raise NotImplementedError
