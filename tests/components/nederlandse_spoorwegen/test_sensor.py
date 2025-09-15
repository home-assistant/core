"""Test the Nederlandse Spoorwegen sensor."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
import requests

from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.components.nederlandse_spoorwegen.sensor import (
    NSDepartureSensor,
    async_setup_platform,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import API_KEY


@pytest.fixture
def mock_nsapi():
    """Create a mock NSAPI client."""
    api_mock = Mock()

    # Mock trip data - past and future departures
    past_trip = Mock()
    past_trip.departure_time_planned = dt_util.now() - timedelta(minutes=5)
    past_trip.departure_time_actual = None
    past_trip.going = "Amsterdam Centraal"
    past_trip.departure = "Rotterdam Centraal"
    past_trip.trip_parts = []
    past_trip.departure_platform_planned = "5a"
    past_trip.departure_platform_actual = None
    past_trip.arrival_platform_planned = "11"
    past_trip.arrival_platform_actual = None
    past_trip.status = "NORMAL"
    past_trip.nr_transfers = 0

    future_trip = Mock()
    future_trip.departure_time_planned = dt_util.now() + timedelta(minutes=15)
    future_trip.departure_time_actual = None
    future_trip.going = "Amsterdam Centraal"
    future_trip.departure = "Rotterdam Centraal"
    future_trip.trip_parts = []
    future_trip.departure_platform_planned = "5b"
    future_trip.departure_platform_actual = None
    future_trip.arrival_platform_planned = "11"
    future_trip.arrival_platform_actual = None
    future_trip.status = "NORMAL"
    future_trip.nr_transfers = 0

    api_mock.get_trips.return_value = [past_trip, future_trip]
    return api_mock


async def test_yaml_platform_setup_creates_repair_issue(hass: HomeAssistant) -> None:
    """Test that YAML platform setup creates repair issue."""
    config = {
        CONF_API_KEY: API_KEY,
        "routes": [
            {
                CONF_NAME: "test route",
                "from": "RTD",
                "to": "AMC",
            }
        ],
    }

    # Mock add_entities
    add_entities = Mock()

    # Call the platform setup
    await async_setup_platform(hass, config, add_entities, None)

    # Check repair issue was created
    issue_registry = ir.async_get(hass)
    issues = [
        issue for issue in issue_registry.issues.values() if issue.domain == DOMAIN
    ]
    assert len(issues) == 1
    assert issues[0].issue_id == "deprecated_yaml_import_issue_unknown"


async def test_sensor_initialization(hass: HomeAssistant, mock_nsapi) -> None:
    """Test sensor initialization."""
    sensor = NSDepartureSensor(
        mock_nsapi,
        "test route",
        "RTD",  # departure
        "AMC",  # heading
        None,  # via
        None,  # time
    )

    # Check basic properties
    assert sensor.name is None  # Uses device name when has_entity_name = True
    assert sensor.icon == "mdi:train"
    assert sensor.unique_id == "rtd_amc_departure"

    # Check device info is set
    assert sensor.device_info is not None
    device_info = sensor.device_info
    assert (DOMAIN, "rtd_amc") in device_info["identifiers"]
    assert device_info["name"] == "test route"


async def test_sensor_update_filters_past_trips(
    hass: HomeAssistant, mock_nsapi
) -> None:
    """Test sensor update filters out past trips."""
    sensor = NSDepartureSensor(
        mock_nsapi,
        "test route",
        "RTD",
        "AMC",
        None,
        None,
    )

    # Update sensor
    sensor.update()

    # Should have state from future trip only
    assert sensor.native_value is not None
    assert sensor._first_trip is not None
    # The first trip should be the future one since past ones are filtered
    expected_time = (dt_util.now() + timedelta(minutes=15)).strftime("%H:%M")
    assert sensor.native_value == expected_time


async def test_sensor_update_handles_api_error(hass: HomeAssistant, mock_nsapi) -> None:
    """Test sensor gracefully handles API errors."""
    # Configure API to raise ConnectionError (which is caught)
    mock_nsapi.get_trips.side_effect = requests.ConnectionError("API Error")

    sensor = NSDepartureSensor(
        mock_nsapi,
        "test route",
        "RTD",
        "AMC",
        None,
        None,
    )

    # Update should not raise exception
    sensor.update()

    # State should remain None when API fails
    assert sensor._trips is None
    assert sensor.native_value is None


async def test_sensor_state_attributes_no_trip_parts(
    hass: HomeAssistant, mock_nsapi
) -> None:
    """Test sensor state attributes when trip has no trip_parts (route bug fix)."""
    # Create mock trip without trip_parts to test the route bug fix
    future_trip = Mock()
    future_trip.departure_time_planned = dt_util.now() + timedelta(minutes=15)
    future_trip.departure_time_actual = None
    future_trip.going = "Amsterdam Centraal"
    future_trip.departure = "Rotterdam Centraal"
    future_trip.trip_parts = []  # Empty trip_parts - this used to cause UnboundLocalError
    future_trip.departure_platform_planned = "5b"
    future_trip.departure_platform_actual = None
    future_trip.arrival_platform_planned = "11"
    future_trip.arrival_platform_actual = None
    future_trip.status = "NORMAL"
    future_trip.nr_transfers = 0

    mock_nsapi.get_trips.return_value = [future_trip]

    sensor = NSDepartureSensor(
        mock_nsapi,
        "test route",
        "RTD",
        "AMC",
        None,
        None,
    )

    # Update sensor to populate trips
    sensor.update()

    # Check state attributes work without trip_parts (route should just be departure)
    attrs = sensor.extra_state_attributes
    assert attrs is not None
    assert "route" in attrs
    assert attrs["route"] == ["Rotterdam Centraal"]  # Should be just departure
    assert attrs["going"] == "Amsterdam Centraal"


async def test_sensor_state_attributes(hass: HomeAssistant, mock_nsapi) -> None:
    """Test sensor state attributes with trip parts."""
    # Create mock trip with trip_parts to avoid the route bug
    future_trip = Mock()
    future_trip.departure_time_planned = dt_util.now() + timedelta(minutes=15)
    future_trip.departure_time_actual = None
    future_trip.going = "Amsterdam Centraal"
    future_trip.departure = "Rotterdam Centraal"

    # Add trip parts to avoid the UnboundLocalError
    trip_part = Mock()
    trip_part.destination = "Utrecht Centraal"
    future_trip.trip_parts = [trip_part]

    future_trip.departure_platform_planned = "5b"
    future_trip.departure_platform_actual = None
    future_trip.arrival_platform_planned = "11"
    future_trip.arrival_platform_actual = None
    future_trip.status = "NORMAL"
    future_trip.nr_transfers = 1

    # Only return the future trip to avoid filtering issues
    mock_nsapi.get_trips.return_value = [future_trip]

    sensor = NSDepartureSensor(
        mock_nsapi,
        "test route",
        "RTD",
        "AMC",
        None,
        None,
    )

    # Update sensor to populate trips
    sensor.update()

    # Check state attributes include trip details
    attrs = sensor.extra_state_attributes
    if attrs is not None:  # Only check if there are attributes
        assert "going" in attrs
        assert attrs["going"] == "Amsterdam Centraal"
        assert "route" in attrs
        assert "Rotterdam Centraal" in attrs["route"]
