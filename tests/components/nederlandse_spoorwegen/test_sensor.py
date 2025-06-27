"""Test the Nederlandse Spoorwegen sensor logic."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from homeassistant.components.nederlandse_spoorwegen.sensor import NSDepartureSensor

FIXED_NOW = datetime(2023, 1, 1, 12, 0, 0)


@pytest.fixture
def mock_nsapi():
    """Mock NSAPI client."""
    nsapi = MagicMock()
    nsapi.get_stations.return_value = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    return nsapi


@pytest.fixture
def mock_trip():
    """Mock a trip object."""
    trip = MagicMock()
    trip.departure = "AMS"
    trip.going = "Utrecht"
    trip.status = "ON_TIME"
    trip.nr_transfers = 0
    trip.trip_parts = []
    trip.departure_time_planned = FIXED_NOW + timedelta(minutes=10)
    trip.departure_time_actual = None
    trip.departure_platform_planned = "5"
    trip.departure_platform_actual = "5"
    trip.arrival_time_planned = FIXED_NOW + timedelta(minutes=40)
    trip.arrival_time_actual = None
    trip.arrival_platform_planned = "8"
    trip.arrival_platform_actual = "8"
    return trip


@pytest.fixture
def mock_trip_delayed():
    """Mock a delayed trip object."""
    trip = MagicMock()
    trip.departure = "AMS"
    trip.going = "Utrecht"
    trip.status = "DELAYED"
    trip.nr_transfers = 1
    trip.trip_parts = []
    trip.departure_time_planned = FIXED_NOW + timedelta(minutes=10)
    trip.departure_time_actual = FIXED_NOW + timedelta(minutes=15)
    trip.departure_platform_planned = "5"
    trip.departure_platform_actual = "6"
    trip.arrival_time_planned = FIXED_NOW + timedelta(minutes=40)
    trip.arrival_time_actual = FIXED_NOW + timedelta(minutes=45)
    trip.arrival_platform_planned = "8"
    trip.arrival_platform_actual = "9"
    return trip


def test_sensor_attributes(mock_nsapi, mock_trip) -> None:
    """Test sensor attributes are set correctly."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = [mock_trip]
    sensor._first_trip = mock_trip
    sensor._next_trip = None
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["going"] == "Utrecht"
    assert attrs["departure_platform_planned"] == "5"
    assert attrs["arrival_platform_planned"] == "8"
    assert attrs["status"] == "on_time"
    assert attrs["transfers"] == 0
    assert attrs["route"] == ["AMS"]


def test_sensor_native_value(mock_nsapi, mock_trip) -> None:
    """Test native_value returns the correct state."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._state = "12:34"
    assert sensor.native_value == "12:34"


def test_sensor_next_trip(mock_nsapi, mock_trip, mock_trip_delayed) -> None:
    """Test extra_state_attributes with next_trip present."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = [mock_trip, mock_trip_delayed]
    sensor._first_trip = mock_trip
    sensor._next_trip = mock_trip_delayed
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["next"] == mock_trip_delayed.departure_time_actual.strftime("%H:%M")


def test_sensor_unavailable(mock_nsapi) -> None:
    """Test extra_state_attributes returns None if no trips."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = None
    sensor._first_trip = None
    assert sensor.extra_state_attributes is None


def test_sensor_delay_logic(mock_nsapi, mock_trip_delayed) -> None:
    """Test delay logic for departure and arrival."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = [mock_trip_delayed]
    sensor._first_trip = mock_trip_delayed
    sensor._next_trip = None
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["departure_delay"] is True
    assert attrs["arrival_delay"] is True
    assert attrs["departure_time_planned"] != attrs["departure_time_actual"]
    assert attrs["arrival_time_planned"] != attrs["arrival_time_actual"]
