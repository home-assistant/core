"""Test the Nederlandse Spoorwegen sensor logic."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
import requests

from homeassistant.components.nederlandse_spoorwegen import sensor as ns_sensor
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


def test_sensor_trip_parts_route(mock_nsapi, mock_trip) -> None:
    """Test route attribute with multiple trip_parts."""
    part1 = MagicMock(destination="HLD")
    part2 = MagicMock(destination="EHV")
    mock_trip.trip_parts = [part1, part2]
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = [mock_trip]
    sensor._first_trip = mock_trip
    sensor._next_trip = None
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["route"] == ["AMS", "HLD", "EHV"]


def test_sensor_missing_optional_fields(mock_nsapi) -> None:
    """Test attributes when optional fields are None."""
    trip = MagicMock()
    trip.departure = "AMS"
    trip.going = "Utrecht"
    trip.status = "ON_TIME"
    trip.nr_transfers = 0
    trip.trip_parts = []
    trip.departure_time_planned = None
    trip.departure_time_actual = None
    trip.departure_platform_planned = None
    trip.departure_platform_actual = None
    trip.arrival_time_planned = None
    trip.arrival_time_actual = None
    trip.arrival_platform_planned = None
    trip.arrival_platform_actual = None
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = [trip]
    sensor._first_trip = trip
    sensor._next_trip = None
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["departure_time_planned"] is None
    assert attrs["departure_time_actual"] is None
    assert attrs["arrival_time_planned"] is None
    assert attrs["arrival_time_actual"] is None
    assert attrs["departure_platform_planned"] is None
    assert attrs["arrival_platform_planned"] is None
    assert attrs["departure_delay"] is False
    assert attrs["arrival_delay"] is False


def test_sensor_multiple_transfers(mock_nsapi, mock_trip) -> None:
    """Test attributes with multiple transfers."""
    mock_trip.nr_transfers = 3
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = [mock_trip]
    sensor._first_trip = mock_trip
    sensor._next_trip = None
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["transfers"] == 3


def test_sensor_next_trip_no_actual_time(
    mock_nsapi, mock_trip, mock_trip_delayed
) -> None:
    """Test next attribute uses planned time if actual is None."""
    mock_trip_delayed.departure_time_actual = None
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = [mock_trip, mock_trip_delayed]
    sensor._first_trip = mock_trip
    sensor._next_trip = mock_trip_delayed
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["next"] == mock_trip_delayed.departure_time_planned.strftime("%H:%M")


def test_sensor_extra_state_attributes_error_handling(mock_nsapi) -> None:
    """Test extra_state_attributes returns None if _first_trip is None or _trips is falsy."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = []
    sensor._first_trip = None
    assert sensor.extra_state_attributes is None
    sensor._trips = None
    assert sensor.extra_state_attributes is None


def test_sensor_status_lowercase(mock_nsapi, mock_trip) -> None:
    """Test status is always lowercased in attributes."""
    mock_trip.status = "DELAYED"
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = [mock_trip]
    sensor._first_trip = mock_trip
    sensor._next_trip = None
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["status"] == "delayed"


def test_sensor_platforms_differ(mock_nsapi, mock_trip) -> None:
    """Test platform planned and actual differ."""
    mock_trip.departure_platform_planned = "5"
    mock_trip.departure_platform_actual = "6"
    mock_trip.arrival_platform_planned = "8"
    mock_trip.arrival_platform_actual = "9"
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    sensor._trips = [mock_trip]
    sensor._first_trip = mock_trip
    sensor._next_trip = None
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert attrs["departure_platform_planned"] != attrs["departure_platform_actual"]
    assert attrs["arrival_platform_planned"] != attrs["arrival_platform_actual"]


def test_valid_stations_all_valid() -> None:
    """Test valid_stations returns True when all stations are valid."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    assert ns_sensor.valid_stations(stations, ["AMS", "UTR"]) is True


def test_valid_stations_some_invalid(caplog: pytest.LogCaptureFixture) -> None:
    """Test valid_stations returns False and logs warning for invalid station."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    with caplog.at_level("WARNING"):
        assert ns_sensor.valid_stations(stations, ["AMS", "XXX"]) is False
        assert "is not a valid station" in caplog.text


def test_valid_stations_none_ignored() -> None:
    """Test valid_stations ignores None values in given_stations."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    assert ns_sensor.valid_stations(stations, [None, "AMS"]) is True


def test_valid_stations_all_none() -> None:
    """Test valid_stations returns True if all given stations are None."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    assert ns_sensor.valid_stations(stations, [None, None]) is True


def test_update_sets_first_and_next_trip(
    monkeypatch: pytest.MonkeyPatch, mock_nsapi, mock_trip, mock_trip_delayed
) -> None:
    """Test update sets _first_trip, _next_trip, and _state correctly."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    # Patch dt_util.now to FIXED_NOW
    monkeypatch.setattr(
        "homeassistant.components.nederlandse_spoorwegen.sensor.dt_util.now",
        lambda: FIXED_NOW,
    )
    # Patch get_trips to return two trips
    mock_nsapi.get_trips.return_value = [mock_trip, mock_trip_delayed]
    # Set planned/actual times in the future
    mock_trip.departure_time_planned = FIXED_NOW + timedelta(minutes=10)
    mock_trip_delayed.departure_time_actual = FIXED_NOW + timedelta(minutes=20)
    sensor.update()
    assert sensor._first_trip == mock_trip
    assert sensor._next_trip == mock_trip_delayed
    assert sensor._state == (FIXED_NOW + timedelta(minutes=10)).strftime("%H:%M")


def test_update_no_trips(monkeypatch: pytest.MonkeyPatch, mock_nsapi) -> None:
    """Test update sets _first_trip and _state to None if no trips returned."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    monkeypatch.setattr(
        "homeassistant.components.nederlandse_spoorwegen.sensor.dt_util.now",
        lambda: FIXED_NOW,
    )
    mock_nsapi.get_trips.return_value = []
    sensor.update()
    assert sensor._first_trip is None
    assert sensor._state is None


def test_update_all_trips_in_past(
    monkeypatch: pytest.MonkeyPatch, mock_nsapi, mock_trip
) -> None:
    """Test update sets _first_trip and _state to None if all trips are in the past."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    monkeypatch.setattr(
        "homeassistant.components.nederlandse_spoorwegen.sensor.dt_util.now",
        lambda: FIXED_NOW,
    )
    # All trips in the past
    mock_trip.departure_time_planned = FIXED_NOW - timedelta(minutes=10)
    mock_trip.departure_time_actual = None
    mock_nsapi.get_trips.return_value = [mock_trip]
    sensor.update()
    assert sensor._first_trip is None
    assert sensor._state is None


def test_update_handles_connection_error(
    monkeypatch: pytest.MonkeyPatch, mock_nsapi
) -> None:
    """Test update logs error and does not raise on connection error."""
    sensor = NSDepartureSensor(mock_nsapi, "Test Sensor", "AMS", "UTR", None, None)
    monkeypatch.setattr(
        "homeassistant.components.nederlandse_spoorwegen.sensor.dt_util.now",
        lambda: FIXED_NOW,
    )
    mock_nsapi.get_trips.side_effect = requests.exceptions.ConnectionError("fail")
    sensor.update()  # Should not raise
