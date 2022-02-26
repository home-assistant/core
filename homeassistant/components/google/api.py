"""Client library for talking to Google APIs."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from googleapiclient import discovery as google_discovery
from oauth2client.file import Storage

from homeassistant.core import HomeAssistant
from homeassistant.util import dt

_LOGGER = logging.getLogger(__name__)


EVENT_PAGE_SIZE = 100


def _api_time_format(
    time: datetime.datetime | None, default: datetime.datetime | None = None
) -> str | None:
    """Convert a datetime to the api string format."""
    if time is None:
        time = default
    return time.isoformat("T") if time else None


class GoogleCalendarService:
    """Calendar service interface to Google."""

    def __init__(self, hass: HomeAssistant, storage: Storage) -> None:
        """Init the Google Calendar service."""
        self._hass = hass
        self._storage = storage

    def _get_service(self) -> google_discovery.Resource:
        """Get the calendar service from the storage file token."""
        return google_discovery.build("calendar", "v3", credentials=self._storage.get())

    def list_calendars(self) -> list[dict[str, Any]]:
        """Return the list of calendars the user has added to their list."""
        cal_list = self._get_service().calendarList()  # pylint: disable=no-member
        return cal_list.list().execute()["items"]

    def create_event(self, calendar_id: str, event: dict[str, Any]) -> dict[str, Any]:
        """Create an event."""
        events = self._get_service().events()  # pylint: disable=no-member
        return events.insert(calendarId=calendar_id, body=event)

    async def async_list_events(
        self,
        calendar_id: str,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        search: str | None = None,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Return the list of events."""
        return await self._hass.async_add_executor_job(
            self.list_events,
            calendar_id,
            start_time,
            end_time,
            search,
            page_token,
        )

    def list_events(
        self,
        calendar_id: str,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        search: str | None = None,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Return the list of events."""
        events = self._get_service().events()  # pylint: disable=no-member
        result = events.list(
            calendarId=calendar_id,
            start_time=_api_time_format(start_time, default=dt.now()),
            end_time=_api_time_format(start_time),
            q=search,
            maxResults=EVENT_PAGE_SIZE,
            pageToken=page_token,
        ).execute()
        return (result["items"], result.get("nextPageToken"))
