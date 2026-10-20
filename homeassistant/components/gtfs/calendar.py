"""Calendar platform for GTFS routes."""

import datetime as dt
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

LOOKAHEAD = dt.timedelta(days=7)
# Covers trips that departed before now and haven't arrived yet.
LOOKBACK = dt.timedelta(days=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GtfsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a calendar for each route subentry."""
    stops = await hass.async_add_executor_job(list_stops, entry.runtime_data)
    for subentry_id, subentry in entry.subentries.items():
        async_add_entities(
            [GtfsRouteCalendar(entry.runtime_data, subentry, stops)],
            update_before_add=True,
            config_subentry_id=subentry_id,
        )


class GtfsRouteCalendar(CalendarEntity):
    """Departures from a route's origin to its destination."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, feed: GtfsFeed, subentry: ConfigSubentry, stops: dict[str, str]
    ) -> None:
        """Initialize the calendar."""
        self._feed = feed
        self._origin = subentry.data[CONF_ORIGIN]
        self._destination = subentry.data[CONF_DESTINATION]
        self._origin_name = stops[self._origin]
        self._destination_name = stops[self._destination]
        self._event: CalendarEvent | None = None
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the current or next departure."""
        return self._event

    async def async_update(self) -> None:
        """Find the current or next departure."""
        now = dt_util.now()
        upcoming = await self.hass.async_add_executor_job(
            self._departures, now - LOOKBACK, now + LOOKAHEAD
        )
        self._event = next(
            (self._to_event(item) for item in upcoming if item.arrival > now), None
        )

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: dt.datetime, end_date: dt.datetime
    ) -> list[CalendarEvent]:
        """Return departures between start_date and end_date."""
        found = await hass.async_add_executor_job(
            self._departures, start_date, end_date
        )
        return [self._to_event(item) for item in found]

    def _departures(self, start: dt.datetime, end: dt.datetime) -> list[Departure]:
        with self._feed.lock:
            schedule = self._feed.schedule
            return departures(
                schedule,
                self._origin,
                self._destination,
                start,
                end,
                feed_time_zone(schedule),
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
