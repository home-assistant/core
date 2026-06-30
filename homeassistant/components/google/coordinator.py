"""Support for Google Calendar Search binary sensors."""

from collections.abc import Iterable
from datetime import datetime, timedelta
import itertools
import logging
from typing import override

from gcal_sync.api import GoogleCalendarService, ListEventsRequest
from gcal_sync.exceptions import ApiException
from gcal_sync.model import Event
from gcal_sync.sync import CalendarEventSyncManager
from gcal_sync.timeline import Timeline, calendar_timeline
from ical.iter import SortableItemValue

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .store import GoogleConfigEntry

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)
# Maximum number of upcoming events to consider for state changes between
# coordinator updates.
MAX_UPCOMING_EVENTS = 20

# Bounds of the locally cached window for query based calendars (search or
# free-busy). Requests within this window are served from the cache to avoid a
# live API request on every call (e.g. calendar cards reloading on the frontend).
QUERY_EVENT_MIN_TIME = timedelta(days=-90)
QUERY_EVENT_MAX_TIME = timedelta(days=90)


def _truncate_timeline(timeline: Timeline, max_events: int) -> Timeline:
    """Truncate the timeline to a maximum number of events.

    This is used to avoid repeated expansion of recurring events during
    state machine updates.
    """
    upcoming = timeline.active_after(dt_util.now())
    truncated = list(itertools.islice(upcoming, max_events))
    return Timeline(
        [
            SortableItemValue(event.timespan_of(dt_util.get_default_time_zone()), event)
            for event in truncated
        ]
    )


class CalendarSyncUpdateCoordinator(DataUpdateCoordinator[Timeline]):
    """Coordinator for calendar RPC calls that use an efficient sync."""

    config_entry: GoogleConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleConfigEntry,
        sync: CalendarEventSyncManager,
        name: str,
    ) -> None:
        """Create the CalendarSyncUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.sync = sync
        self._upcoming_timeline: Timeline | None = None

    @override
    async def _async_update_data(self) -> Timeline:
        """Fetch data from API endpoint."""
        try:
            await self.sync.run()
        except ApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        timeline = await self.sync.store_service.async_get_timeline(
            dt_util.get_default_time_zone()
        )
        self._upcoming_timeline = _truncate_timeline(timeline, MAX_UPCOMING_EVENTS)
        return timeline

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> Iterable[Event]:
        """Get all events in a specific time frame."""
        if not self.data:
            raise HomeAssistantError(
                "Unable to get events: Sync from server has not completed"
            )
        return self.data.overlapping(
            start_date,
            end_date,
        )

    @property
    def upcoming(self) -> Iterable[Event] | None:
        """Return upcoming events if any."""
        if self._upcoming_timeline:
            return self._upcoming_timeline.active_after(dt_util.now())
        return None


class CalendarQueryUpdateCoordinator(DataUpdateCoordinator[list[Event]]):
    """Coordinator for calendar RPC calls.

    This sends a polling RPC, not using sync, as a workaround
    for limitations in the calendar API for supporting search.
    """

    config_entry: GoogleConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleConfigEntry,
        calendar_service: GoogleCalendarService,
        name: str,
        calendar_id: str,
        search: str | None,
    ) -> None:
        """Create the CalendarQueryUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self._search = search
        self._timeline: Timeline | None = None
        self._upcoming_timeline: Timeline | None = None
        self._cache_start: datetime | None = None
        self._cache_end: datetime | None = None

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> Iterable[Event]:
        """Get all events in a specific time frame."""
        # Serve from the locally cached window when possible to avoid a live API
        # request on every call.
        if (
            self._timeline is not None
            and self._cache_start is not None
            and self._cache_end is not None
            and start_date >= self._cache_start
            and end_date <= self._cache_end
        ):
            return self._timeline.overlapping(start_date, end_date)
        try:
            return await self._async_fetch_events(start_date, end_date)
        except ApiException as err:
            self.async_set_update_error(err)
            raise HomeAssistantError(str(err)) from err

    async def _async_fetch_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[Event]:
        """Query the API for events in a specific time frame."""
        request = ListEventsRequest(
            calendar_id=self.calendar_id,
            start_time=start_date,
            end_time=end_date,
            search=self._search,
        )
        result_items: list[Event] = []
        result = await self.calendar_service.async_list_events(request)
        async for result_page in result:
            result_items.extend(result_page.items)
        return result_items

    @override
    async def _async_update_data(self) -> list[Event]:
        """Fetch data from API endpoint."""
        start_time = dt_util.now() + QUERY_EVENT_MIN_TIME
        end_time = dt_util.now() + QUERY_EVENT_MAX_TIME
        try:
            result_items = await self._async_fetch_events(start_time, end_time)
        except ApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        timeline = calendar_timeline(result_items, dt_util.get_default_time_zone())
        self._timeline = timeline
        self._upcoming_timeline = _truncate_timeline(timeline, MAX_UPCOMING_EVENTS)
        self._cache_start = start_time
        self._cache_end = end_time
        return result_items

    @property
    def upcoming(self) -> Iterable[Event] | None:
        """Return upcoming events if any."""
        if self._upcoming_timeline:
            return self._upcoming_timeline.active_after(dt_util.now())
        return None
