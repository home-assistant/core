"""Utility functions for Nederlandse Spoorwegen integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ns_api import Trip


def get_planned_departure_platform(trip: Trip) -> str | None:
    """Get planned departure platform from trip data."""
    return trip.departure_platform_planned


def get_actual_departure_platform(trip: Trip) -> str | None:
    """Get actual departure platform from trip data."""
    return trip.departure_platform_actual


def get_planned_arrival_platform(trip: Trip) -> str | None:
    """Get planned arrival platform from trip data."""
    return trip.arrival_platform_planned


def get_actual_arrival_platform(trip: Trip) -> str | None:
    """Get actual arrival platform from trip data."""
    return trip.arrival_platform_actual


def get_planned_departure_time(trip: Trip) -> datetime | None:
    """Get planned departure time from trip data."""
    return getattr(trip, "departure_time_planned", None)


def get_actual_departure_time(trip: Trip) -> datetime | None:
    """Get actual departure time from trip data."""
    return getattr(trip, "departure_time_actual", None)


def get_planned_arrival_time(trip: Trip) -> datetime | None:
    """Get planned arrival time from trip data."""
    return getattr(trip, "arrival_time_planned", None)


def get_actual_arrival_time(trip: Trip) -> datetime | None:
    """Get actual arrival time from trip data."""
    return getattr(trip, "arrival_time_actual", None)


def get_planned_departure_time_str(trip: Trip) -> str | None:
    """Get planned departure time from trip data."""
    planned_time = get_planned_departure_time(trip)
    return planned_time.strftime("%H:%M") if planned_time else None


def get_actual_departure_time_str(trip: Trip) -> str | None:
    """Get actual departure time from trip data."""
    actual_time = get_actual_departure_time(trip)
    return actual_time.strftime("%H:%M") if actual_time else None


def get_planned_arrival_time_str(trip: Trip) -> str | None:
    """Get planned arrival time from trip data."""
    planned_time = get_planned_arrival_time(trip)
    return planned_time.strftime("%H:%M") if planned_time else None


def get_actual_arrival_time_str(trip: Trip) -> str | None:
    """Get actual arrival time from trip data."""
    actual_time = get_actual_arrival_time(trip)
    return actual_time.strftime("%H:%M") if actual_time else None


def get_status(trip: Trip) -> str | None:
    """Get status from trip data."""
    return getattr(trip, "status", None)


def get_transfers(trip: Trip) -> int:
    """Get number of transfers from trip data."""
    return getattr(trip, "nr_transfers", 0)


def get_departure_time(trip: Trip) -> datetime | None:
    """Get next departure time from trip data."""
    return get_actual_departure_time(trip) or get_planned_departure_time(trip)


def get_departure_time_str(trip: Trip) -> str | None:
    """Get next departure time from trip data."""
    departure_time = get_departure_time(trip)
    return departure_time.strftime("%H:%M") if departure_time else None


def get_route(trip: Trip) -> list[str]:
    """Get the route as a list of station names from trip data."""
    trip_parts = trip.trip_parts or []
    if not trip_parts:
        return []
    route = []
    departure = trip.departure
    if departure:
        route.append(departure)
    route.extend(part.destination for part in trip_parts)
    return route


def get_going(trip: Trip) -> bool | None:
    """Get the 'going' attribute from trip data."""
    return getattr(trip, "going", None)


def get_arrival_delay(trip: Trip) -> bool:
    """Return True if arrival is delayed, False otherwise."""
    planned = get_planned_arrival_time(trip)
    actual = get_actual_arrival_time(trip)
    return bool(planned and actual and planned != actual)


def get_departure_delay(trip: Trip) -> bool:
    """Return True if departure is delayed, False otherwise."""
    planned = get_planned_departure_time(trip)
    actual = get_actual_departure_time(trip)
    return bool(planned and actual and planned != actual)


def get_coordinator_attribute(coordinator, attribute: str) -> Any:
    """Get attribute from coordinator data with error handling."""
    if not coordinator:
        return None
    return getattr(coordinator, attribute, None)


def get_coordinator_data_attribute(coordinator, attribute: str) -> Any:
    """Get attribute from coordinator.data with error handling."""
    data = get_coordinator_attribute(coordinator, "data")
    if not data or not hasattr(data, attribute):
        return None
    return getattr(data, attribute, None)
