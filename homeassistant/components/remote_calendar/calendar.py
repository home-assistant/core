"""Calendar platform for a Remote Calendar."""

from datetime import datetime
import itertools
import logging

from ical.event import Event

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import RemoteCalendarConfigEntry
from .const import CONF_CALENDAR_NAME
from .coordinator import SCAN_INTERVAL, RemoteCalendarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

# Safety limit to prevent unbounded iteration over malformed calendars
# with excessive overlapping events in the same time window.
_UPCOMING_EVENTS_CACHE_LIMIT = 200


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemoteCalendarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the remote calendar platform."""
    coordinator = entry.runtime_data
    entity = RemoteCalendarEntity(coordinator, entry)
    async_add_entities([entity], True)


class RemoteCalendarEntity(
    CoordinatorEntity[RemoteCalendarDataUpdateCoordinator], CalendarEntity
):
    """A calendar entity backed by a remote iCalendar url."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RemoteCalendarDataUpdateCoordinator,
        entry: RemoteCalendarConfigEntry,
    ) -> None:
        """Initialize RemoteCalendarEntity."""
        super().__init__(coordinator)
        self._attr_name = entry.data[CONF_CALENDAR_NAME]
        self._attr_unique_id = entry.entry_id
        self._upcoming_events: list[CalendarEvent] = []

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        for event in self._upcoming_events:
            if now < event.end_datetime_local:
                return event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""

        def events_in_range() -> list[CalendarEvent]:
            """Return all events in the given time range."""
            events = self.coordinator.data.timeline_tz(start_date.tzinfo).overlapping(
                start_date,
                end_date,
            )
            return [_get_calendar_event(event) for event in events]

        return await self.hass.async_add_executor_job(events_in_range)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.hass.async_create_task(self._async_rebuild_and_write_state())

    async def _async_rebuild_and_write_state(self) -> None:
        """Rebuild upcoming events cache and write state."""
        await self._async_rebuild_upcoming_events()
        self.async_write_ha_state()

    async def _async_rebuild_upcoming_events(self) -> None:
        """Rebuild the upcoming events cache from coordinator data."""

        def upcoming_events() -> list[CalendarEvent]:
            now = dt_util.now()
            upcoming: list[CalendarEvent] = []
            for event in itertools.islice(
                self.coordinator.data.timeline_tz(now.tzinfo).active_after(now),
                _UPCOMING_EVENTS_CACHE_LIMIT,
            ):
                cal_event = _get_calendar_event(event)
                upcoming.append(cal_event)
                if cal_event.start_datetime_local >= now + SCAN_INTERVAL:
                    break
            if len(upcoming) >= _UPCOMING_EVENTS_CACHE_LIMIT:
                _LOGGER.warning(
                    "Upcoming events cache limit (%s) reached; some events"
                    " may not be cached",
                    _UPCOMING_EVENTS_CACHE_LIMIT,
                )
            return upcoming

        self._upcoming_events = await self.hass.async_add_executor_job(upcoming_events)

    async def async_update(self) -> None:
        """Refresh the timeline.

        This is called when the coordinator updates. Creating the timeline may
        require walking through the entire calendar and handling recurring
        events, so it is done as a separate task without blocking the event loop.
        """
        await super().async_update()
        await self._async_rebuild_upcoming_events()


def _get_calendar_event(event: Event) -> CalendarEvent:
    """Return a CalendarEvent from an API event."""

    return CalendarEvent(
        summary=event.summary or "",
        start=(
            dt_util.as_local(event.start)
            if isinstance(event.start, datetime)
            else event.start
        ),
        end=(
            dt_util.as_local(event.end)
            if isinstance(event.end, datetime)
            else event.end
        ),
        description=event.description,
        uid=event.uid,
        rrule=event.rrule.as_rrule_str() if event.rrule else None,
        recurrence_id=event.recurrence_id,
        location=event.location,
    )
