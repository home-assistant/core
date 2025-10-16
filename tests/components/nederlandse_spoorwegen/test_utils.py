"""Unit tests for Nederlandse Spoorwegen utils."""

from datetime import datetime

from ns_api import Trip

from homeassistant.components.nederlandse_spoorwegen.utils import (
    get_arrival_delay,
    get_departure_delay,
)


def _make_trip(planned=None, actual=None) -> Trip:
    trip = Trip()
    if planned:
        trip.departure_time_planned = planned
        trip.arrival_time_planned = planned
    if actual:
        trip.departure_time_actual = actual
        trip.arrival_time_actual = actual
    return trip


def test_departure_delay_planned_only() -> None:
    """Test departure delay with planned time only."""
    planned = datetime(2025, 10, 16, 8, 0)
    trip = _make_trip(planned=planned)
    assert not get_departure_delay(trip)  # There is no delay


def test_departure_delay_actual_only() -> None:
    """Test departure delay with actual time only."""
    actual = datetime(2025, 10, 16, 8, 5)
    trip = _make_trip(actual=actual)
    assert not get_departure_delay(trip)  # There is no delay


def test_departure_delay_equal() -> None:
    """Test departure delay with equal planned and actual times."""
    planned = actual = datetime(2025, 10, 16, 8, 0)
    trip = _make_trip(planned=planned, actual=actual)
    assert not get_departure_delay(trip)  # There is no delay


def test_departure_delay_different() -> None:
    """Test departure delay with different planned and actual times."""
    planned = datetime(2025, 10, 16, 8, 0)
    actual = datetime(2025, 10, 16, 8, 10)
    trip = _make_trip(planned=planned, actual=actual)
    assert get_departure_delay(trip)  # There is a delay


def test_arrival_delay_planned_only() -> None:
    """Test arrival delay with planned time only."""
    planned = datetime(2025, 10, 16, 9, 0)
    trip = _make_trip(planned=planned)
    assert not get_arrival_delay(trip)  # There is no delay


def test_arrival_delay_actual_only() -> None:
    """Test arrival delay with actual time only."""
    actual = datetime(2025, 10, 16, 9, 5)
    trip = _make_trip(actual=actual)
    assert not get_arrival_delay(trip)  # There is no delay


def test_arrival_delay_equal() -> None:
    """Test arrival delay with equal planned and actual times."""
    planned = actual = datetime(2025, 10, 16, 9, 0)
    trip = _make_trip(planned=planned, actual=actual)
    assert not get_arrival_delay(trip)  # There is no delay


def test_arrival_delay_different() -> None:
    """Test arrival delay with different planned and actual times."""
    planned = datetime(2025, 10, 16, 9, 0)
    actual = datetime(2025, 10, 16, 9, 15)
    trip = _make_trip(planned=planned, actual=actual)
    assert get_arrival_delay(trip)  # There is a delay
