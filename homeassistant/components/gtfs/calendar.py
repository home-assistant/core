"""Calendar platform for GTFS routes."""

import datetime as dt
import itertools
from typing import override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_DESTINATION, CONF_ORIGIN, DOMAIN
from .feed import GtfsConfigEntry, GtfsFeed, list_stops
from .timetable import Departure, departures, feed_time_zone

PARALLEL_UPDATES = 1
# The schedule is static; the event property steps through cached departures.
SCAN_INTERVAL = dt.timedelta(minutes=15)

LOOKAHEAD = dt.timedelta(days=7)
# Covers trips that departed before now and haven't arrived yet.
LOOKBACK = dt.timedelta(days=1)
MAX_UPCOMING = 20


def _load_feed_info(feed: GtfsFeed) -> tuple[dict[str, str], dt.tzinfo]:
    stops = list_stops(feed)
    with feed.lock:
        return stops, feed_time_zone(feed.schedule)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GtfsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a calendar for each route subentry."""
    stops, time_zone = await hass.async_add_executor_job(
        _load_feed_info, entry.runtime_data
    )
    for subentry_id, subentry in entry.subentries.items():
        async_add_entities(
            [GtfsRouteCalendar(entry.runtime_data, subentry, stops, time_zone)],
            update_before_add=True,
            config_subentry_id=subentry_id,
        )


class GtfsRouteCalendar(CalendarEntity):
    """Departures from a route's origin to its destination."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        feed: GtfsFeed,
        subentry: ConfigSubentry,
        stops: dict[str, str],
        time_zone: dt.tzinfo,
    ) -> None:
        """Initialize the calendar."""
        self._feed = feed
        self._origin = subentry.data[CONF_ORIGIN]
        self._destination = subentry.data[CONF_DESTINATION]
        self._origin_name = stops.get(self._origin, self._origin)
        self._destination_name = stops.get(self._destination, self._destination)
        self._time_zone = time_zone
        self._upcoming: list[CalendarEvent] = []
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the current or next departure.

        The calendar's own alarms step through the cache between polls.
        """
        now = dt_util.now()
        return next(
            (event for event in self._upcoming if event.end_datetime_local > now), None
        )

    async def async_update(self) -> None:
        """Cache the upcoming departures."""
        self._upcoming = await self.hass.async_add_executor_job(self._find_upcoming)

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: dt.datetime, end_date: dt.datetime
    ) -> list[CalendarEvent]:
        """Return departures between start_date and end_date."""
        return await hass.async_add_executor_job(self._events, start_date, end_date)

    def _find_upcoming(self) -> list[CalendarEvent]:
        now = dt_util.now()
        found = self._departures(now - LOOKBACK, now + LOOKAHEAD)
        return [
            self._to_event(item)
            for item in itertools.islice(
                (item for item in found if item.arrival > now), MAX_UPCOMING
            )
        ]

    def _events(self, start: dt.datetime, end: dt.datetime) -> list[CalendarEvent]:
        return [self._to_event(item) for item in self._departures(start, end)]

    def _departures(self, start: dt.datetime, end: dt.datetime) -> list[Departure]:
        with self._feed.lock:
            schedule = self._feed.schedule
            return departures(
                schedule,
                self._origin,
                self._destination,
                start,
                end,
                self._time_zone,
            )

    def _to_event(self, departure: Departure) -> CalendarEvent:
        route = departure.route_short_name or departure.route_long_name
        headsign = departure.headsign or self._destination_name
        return CalendarEvent(
            start=dt_util.as_local(departure.departure),
            end=dt_util.as_local(departure.arrival),
            summary=f"{route} to {headsign}",
            location=self._origin_name,
            description="\n".join(
                filter(
                    None,
                    (
                        departure.route_long_name,
                        departure.agency_name,
                        f"Trip {departure.trip_id}",
                    ),
                )
            ),
            uid=f"{departure.trip_id}-{departure.service_date.isoformat()}",
        )
