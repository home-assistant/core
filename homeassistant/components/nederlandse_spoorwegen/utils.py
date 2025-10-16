"""Utility functions for Nederlandse Spoorwegen integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ns_api import Trip


def get_planned_departure_platform(data: Trip) -> str | None:
    """Get planned departure platform from trip data."""
    return _get_trip_attribute(data, "departure_platform_planned")


def get_actual_departure_platform(data: Trip) -> str | None:
    """Get actual departure platform from trip data."""
    return _get_trip_attribute(data, "departure_platform_actual")


def get_planned_arrival_platform(data: Trip) -> str | None:
    """Get planned arrival platform from trip data."""
    return _get_trip_attribute(data, "arrival_platform_planned")


def get_actual_arrival_platform(data: Trip) -> str | None:
    """Get actual arrival platform from trip data."""
    return _get_trip_attribute(data, "arrival_platform_actual")


def get_planned_departure_time(data: Trip) -> datetime | None:
    """Get planned departure time from trip data."""
    return _get_trip_attribute(data, "departure_time_planned")


def get_actual_departure_time(data: Trip) -> datetime | None:
    """Get actual departure time from trip data."""
    return _get_trip_attribute(data, "departure_time_actual")


def get_planned_arrival_time(data: Trip) -> datetime | None:
    """Get planned arrival time from trip data."""
    return _get_trip_attribute(data, "arrival_time_planned")


def get_actual_arrival_time(data: Trip) -> datetime | None:
    """Get actual arrival time from trip data."""
    return _get_trip_attribute(data, "arrival_time_actual")


def get_planned_departure_time_str(data: Trip) -> str | None:
    """Get planned departure time from trip data."""
    planned_time = get_planned_departure_time(data)
    return planned_time.strftime("%H:%M") if planned_time else None


def get_actual_departure_time_str(data: Trip) -> str | None:
    """Get actual departure time from trip data."""
    actual_time = get_actual_departure_time(data)
    return actual_time.strftime("%H:%M") if actual_time else None


def get_planned_arrival_time_str(data: Trip) -> str | None:
    """Get planned arrival time from trip data."""
    planned_time = get_planned_arrival_time(data)
    return planned_time.strftime("%H:%M") if planned_time else None


def get_actual_arrival_time_str(data: Trip) -> str | None:
    """Get actual arrival time from trip data."""
    actual_time = get_actual_arrival_time(data)
    return actual_time.strftime("%H:%M") if actual_time else None


def get_status(data: Trip) -> str | None:
    """Get status from trip data."""
    status = _get_trip_attribute(data, "status")
    return status.capitalize() if status else None


def get_transfers(data: Trip) -> int:
    """Get number of transfers from trip data."""
    return _get_trip_attribute(data, "nr_transfers") or 0


def get_departure_time(data: Trip) -> datetime | None:
    """Get next departure time from trip data."""
    return _get_trip_attribute(data, "departure_time_actual") or _get_trip_attribute(
        data, "departure_time_planned"
    )


def get_departure_time_str(data: Trip) -> str | None:
    """Get next departure time from trip data."""
    departure_time = get_departure_time(data)
    return departure_time.strftime("%H:%M") if departure_time else None


def get_route(trip: Trip) -> list[str]:
    """Get the route as a list of station names from trip data."""
    route = []
    trip_parts = _get_trip_attribute(trip, "trip_parts", [])
    departure = _get_trip_attribute(trip, "departure")
    if departure:
        route.append(departure)
    if not trip_parts:
        return route
    route.extend(part.destination for part in trip_parts)
    return route


def get_going(trip: Trip) -> bool | None:
    """Get the 'going' attribute from trip data."""
    return _get_trip_attribute(trip, "going")


def get_arrival_delay(trip: Trip) -> bool:
    """Return True if arrival is delayed, False otherwise."""
    planned = get_planned_arrival_time(trip)
    actual = get_actual_arrival_time(trip)
    if planned and actual and planned != actual:
        return True
    return False


def get_departure_delay(trip: Trip) -> bool:
    """Return True if departure is delayed, False otherwise."""
    planned = get_planned_departure_time(trip)
    actual = get_actual_departure_time(trip)
    if planned and actual and planned != actual:
        return True
    return False


def get_coordinator_attribute(coordinator, attribute: str) -> Any:
    """Get attribute from coordinator data with error handling."""
    if not coordinator or not hasattr(coordinator, attribute):
        return None
    return getattr(coordinator, attribute, None)


def get_coordinator_data_attribute(coordinator, attribute: str) -> Any:
    """Get attribute from coordinator.data with error handling."""
    data = get_coordinator_attribute(coordinator, "data")
    if not data or not hasattr(data, attribute):
        return None
    return getattr(data, attribute, None)


def _get_trip_attribute(trip: Trip, attribute: str, default: Any = None) -> Any:
    """Get attribute from trip object with error handling."""

    return getattr(trip, attribute, default)
