"""Coordinator for iCloud Calendars."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any, override

from pyicloud.exceptions import PyiCloudException

from homeassistant.components.calendar import CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .account import IcloudConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)

# How much of the calendar to keep cached for the entity's current/next event.
# `async_get_events` queries iCloud directly for anything outside this window.
LOOKBACK = timedelta(days=1)
LOOKAHEAD = timedelta(days=30)


@dataclass(slots=True)
class IcloudCalendarData:
    """A calendar and the events cached for it."""

    name: str
    events: list[CalendarEvent]


def localize(value: date | datetime) -> datetime:
    """Return a comparable, timezone-aware datetime for a date or datetime."""
    if isinstance(value, datetime):
        return dt_util.as_local(value)
    return dt_util.start_of_local_day(value)


class IcloudCalendarCoordinator(DataUpdateCoordinator[dict[str, IcloudCalendarData]]):
    """Keep a rolling window of events cached for the current/next lookup."""

    def __init__(self, hass: HomeAssistant, entry: IcloudConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.account = entry.runtime_data

    def fetch_events(
        self, start: datetime, end: datetime, guids: list[str] | None = None
    ) -> dict[str, list[CalendarEvent]]:
        """Return events per calendar between two points. Runs in the executor."""
        if (api := self.account.api) is None:
            raise UpdateFailed("iCloud account is not authenticated")

        wanted = set(guids) if guids else None
        result: dict[str, list[CalendarEvent]] = {guid: [] for guid in (wanted or ())}

        for event in api.calendar.get_events(from_dt=start, to_dt=end, as_objs=True):
            guid = getattr(event, "pguid", None)
            if guid is None or (wanted is not None and guid not in wanted):
                continue
            if (parsed := _as_calendar_event(event)) is not None:
                result.setdefault(guid, []).append(parsed)

        for events in result.values():
            events.sort(key=lambda event: localize(event.start))
        return result

    def _fetch(self) -> dict[str, IcloudCalendarData]:
        """Fetch the calendars and their events. Runs in the executor."""
        if (api := self.account.api) is None:
            raise UpdateFailed("iCloud account is not authenticated")

        names = {
            calendar.guid: calendar.title
            for calendar in api.calendar.get_calendars(as_objs=True)
        }
        now = dt_util.now()
        events = self.fetch_events(now - LOOKBACK, now + LOOKAHEAD, list(names))

        return {
            guid: IcloudCalendarData(name=name, events=events.get(guid, []))
            for guid, name in names.items()
        }

    @override
    async def _async_update_data(self) -> dict[str, IcloudCalendarData]:
        """Fetch calendars and their upcoming events."""
        try:
            return await self.hass.async_add_executor_job(self._fetch)
        except PyiCloudException as err:
            raise UpdateFailed(f"Error fetching calendars: {err}") from err


def _parse_apple_date(value: Any) -> datetime | None:
    """Parse the date format iCloud returns for calendar events.

    ``EventObject`` is annotated as holding ``datetime``, but pyicloud hands
    back the wire format unchanged: ``[yyyymmdd, year, month, day, hour,
    minute, minutes_since_midnight]``. Both forms are accepted so this keeps
    working if that is ever changed upstream.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 6:
        try:
            _, year, month, day, hour, minute = value[:6]
            return datetime(int(year), int(month), int(day), int(hour), int(minute))
        except TypeError, ValueError:
            _LOGGER.debug("Unparseable calendar date: %r", value)
    return None


def _as_calendar_event(event: Any) -> CalendarEvent | None:
    """Convert a pyicloud event into a Home Assistant calendar event."""
    start = _parse_apple_date(
        getattr(event, "local_start_date", None)
    ) or _parse_apple_date(getattr(event, "start_date", None))
    if start is None:
        return None

    end = _parse_apple_date(
        getattr(event, "local_end_date", None)
    ) or _parse_apple_date(getattr(event, "end_date", None))
    if end is None:
        end = start + timedelta(hours=1)

    start_value: date | datetime
    end_value: date | datetime
    if getattr(event, "all_day", False):
        start_value = start.date()
        end_value = end.date()
        # Home Assistant treats the end of an all-day event as exclusive.
        if end_value <= start_value:
            end_value = start_value + timedelta(days=1)
    else:
        start_value = dt_util.as_local(start)
        end_value = dt_util.as_local(end)
        if end_value <= start_value:
            end_value = start_value + timedelta(minutes=30)

    return CalendarEvent(
        uid=getattr(event, "guid", None) or None,
        summary=getattr(event, "title", None) or "",
        start=start_value,
        end=end_value,
        location=getattr(event, "location", None) or None,
    )
