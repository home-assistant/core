"""Departures between two stops in an imported GTFS schedule.

Call these functions in the executor while holding the feed's lock: the
SQLAlchemy session isn't thread-safe and time zone lookups may hit the disk.
"""

from dataclasses import dataclass
import datetime as dt
from typing import Any

import pygtfs
from pygtfs.gtfs_entities import (
    Agency,
    Route,
    Service,
    ServiceException,
    StopTime,
    Trip,
)
from sqlalchemy import Row, or_
from sqlalchemy.orm import aliased

from homeassistant.util import dt as dt_util

SERVICE_ADDED = 1
SERVICE_REMOVED = 2
NO_PICKUP = 1
NO_DROP_OFF = 1
WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
# Stop times can run past 24:00 (rarely 48:00) on the previous service day.
LOOKBACK_DAYS = 2


@dataclass(frozen=True, slots=True)
class Departure:
    """A trip from the origin to the destination."""

    departure: dt.datetime
    arrival: dt.datetime
    service_date: dt.date
    trip_id: str
    headsign: str | None
    route_short_name: str | None
    route_long_name: str | None
    agency_name: str | None


def feed_time_zone(schedule: pygtfs.Schedule) -> dt.tzinfo:
    """Return the feed's time zone, which GTFS requires all agencies to share."""
    agency = schedule.agencies_query.first()
    return (
        dt_util.get_time_zone(agency.agency_timezone) or dt_util.get_default_time_zone()
    )


def departures(
    schedule: pygtfs.Schedule,
    origin: str,
    destination: str,
    start: dt.datetime,
    end: dt.datetime,
    time_zone: dt.tzinfo,
) -> list[Departure]:
    """Return trips from origin to destination overlapping [start, end)."""
    first = start.astimezone(time_zone).date() - dt.timedelta(days=LOOKBACK_DAYS)
    # On a day clocks go forward, the next service day starts before midnight.
    last = end.astimezone(time_zone).date() + dt.timedelta(days=1)
    active = _active_services(schedule, first, last)
    trips = _trips(schedule, origin, destination)
    rides: dict[tuple[str, dt.date], Departure] = {}
    for day, services in active.items():
        # GTFS times count from noon minus 12 hours, which stays correct on
        # daylight saving days; the arithmetic must be absolute, so do it in UTC.
        base = dt.datetime.combine(day, dt.time(12), time_zone).astimezone(
            dt.UTC
        ) - dt.timedelta(hours=12)
        for trip in trips:
            if trip.service_id not in services:
                continue
            ride = Departure(
                departure=base + trip.departure_time,
                arrival=base + trip.arrival_time,
                service_date=day,
                trip_id=trip.trip_id,
                headsign=trip.stop_headsign or trip.trip_headsign,
                route_short_name=trip.route_short_name,
                route_long_name=trip.route_long_name,
                agency_name=trip.agency_name,
            )
            # A trip visiting the origin more than once departs on its shortest ride.
            best = rides.get((trip.trip_id, day))
            if best is None or _is_shorter(ride, best):
                rides[trip.trip_id, day] = ride
    found = [
        ride for ride in rides.values() if ride.departure < end and ride.arrival > start
    ]
    found.sort(key=lambda item: (item.departure, item.trip_id))
    return found


def _is_shorter(ride: Departure, other: Departure) -> bool:
    return ride.departure > other.departure or (
        ride.departure == other.departure and ride.arrival < other.arrival
    )


def _active_services(
    schedule: pygtfs.Schedule, first: dt.date, last: dt.date
) -> dict[dt.date, set[str]]:
    days = [
        first + dt.timedelta(days=offset) for offset in range((last - first).days + 1)
    ]
    active: dict[dt.date, set[str]] = {day: set() for day in days}
    services = schedule.session.query(Service).filter(
        Service.start_date <= last, Service.end_date >= first
    )
    for service in services:
        for day in days:
            if service.start_date <= day <= service.end_date and getattr(
                service, WEEKDAYS[day.weekday()]
            ):
                active[day].add(service.service_id)
    exceptions = schedule.session.query(ServiceException).filter(
        ServiceException.date >= first, ServiceException.date <= last
    )
    for exception in exceptions:
        if exception.exception_type == SERVICE_ADDED:
            active[exception.date].add(exception.service_id)
        elif exception.exception_type == SERVICE_REMOVED:
            active[exception.date].discard(exception.service_id)
    return active


def _trips(schedule: pygtfs.Schedule, origin: str, destination: str) -> list[Row[Any]]:
    origin_time = aliased(StopTime)
    destination_time = aliased(StopTime)
    return (
        schedule.session.query(
            Trip.trip_id,
            Trip.service_id,
            Trip.trip_headsign,
            origin_time.stop_headsign,
            origin_time.departure_time,
            destination_time.arrival_time,
            Route.route_short_name,
            Route.route_long_name,
            Agency.agency_name,
        )
        .join(origin_time, origin_time.trip_id == Trip.trip_id)
        .join(destination_time, destination_time.trip_id == Trip.trip_id)
        .join(Route, Route.route_id == Trip.route_id)
        .outerjoin(Agency, Agency.agency_id == Route.agency_id)
        .filter(
            origin_time.stop_id == origin,
            destination_time.stop_id == destination,
            origin_time.stop_sequence < destination_time.stop_sequence,
            origin_time.departure_time.is_not(None),
            destination_time.arrival_time.is_not(None),
            or_(
                origin_time.pickup_type.is_(None), origin_time.pickup_type != NO_PICKUP
            ),
            or_(
                destination_time.drop_off_type.is_(None),
                destination_time.drop_off_type != NO_DROP_OFF,
            ),
        )
        .all()
    )
