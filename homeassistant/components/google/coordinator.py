"""Support for Google Calendar Search binary sensors."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
import itertools
import logging

from gcal_sync.api import GoogleCalendarService, ListEventsRequest
from gcal_sync.exceptions import ApiException
from gcal_sync.model import Event
from gcal_sync.sync import CalendarEventSyncManager
from gcal_sync.timeline import Timeline
from ical.iter import SortableItemValue

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)
# Maximum number of upcoming events to consider for state changes between
# coordinator updates.
MAX_UPCOMING_EVENTS = 20


def _truncate_timeline(timeline: Timeline, max_events: int) -> Timeline:
    """Truncate the timeline to a maximum number of events.

    This is used to avoid repeated expansion of recurring events during
    state machine updates.
    """
    upcoming = timeline.active_after(dt_util.now())
    truncated = list(itertools.islice(upcoming, max_events))
    return Timeline(
        [
            SortableItemValue(event.timespan_of(dt_util.DEFAULT_TIME_ZONE), event)
            for event in truncated
        ]
    )


class CalendarSyncUpdateCoordinator(DataUpdateCoordinator[Timeline]):
    """Coordinator for calendar RPC calls that use an efficient sync."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        sync: CalendarEventSyncManager,
        name: str,
    ) -> None:
        """Create the CalendarSyncUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.sync = sync
        self._upcoming_timeline: Timeline | None = None

    async def _async_update_data(self) -> Timeline:
        """Fetch data from API endpoint."""
        try:
            await self.sync.run()
        except ApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        timeline = await self.sync.store_service.async_get_timeline(
            dt_util.DEFAULT_TIME_ZONE
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

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        calendar_service: GoogleCalendarService,
        name: str,
        calendar_id: str,
        search: str | None,
    ) -> None:
        """Create the CalendarQueryUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=MIN_TIME_BETWEEN_UPDATES,
        )
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self._search = search

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> Iterable[Event]:
        """Get all events in a specific time frame."""
        request = ListEventsRequest(
            calendar_id=self.calendar_id,
            start_time=start_date,
            end_time=end_date,
            search=self._search,
        )
        result_items = []
        try:
            result = await self.calendar_service.async_list_events(request)
            async for result_page in result:
                result_items.extend(result_page.items)
        except ApiException as err:
            self.async_set_update_error(err)
            raise HomeAssistantError(str(err)) from err
        return result_items

    async def _async_update_data(self) -> list[Event]:
        """Fetch data from API endpoint."""
        request = ListEventsRequest(calendar_id=self.calendar_id, search=self._search)
        try:
            result = await self.calendar_service.async_list_events(request)
        except ApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return result.items

    @property
    def upcoming(self) -> Iterable[Event] | None:
        """Return the next upcoming event if any."""
        return self.data
