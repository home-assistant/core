"""Test the Nederlandse Spoorwegen coordinator."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from ns_api import RequestParametersError
import pytest
import requests

from homeassistant.components.nederlandse_spoorwegen import NSRuntimeData
from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_api_wrapper():
    """Mock API wrapper."""
    wrapper = MagicMock()
    wrapper.validate_api_key = AsyncMock(return_value=True)
    wrapper.get_stations = AsyncMock(
        return_value=[
            MagicMock(code="AMS", name="Amsterdam"),
            MagicMock(code="UTR", name="Utrecht"),
        ]
    )

    # Create proper trip mocks with datetime objects
    future_time = datetime.now(UTC).replace(hour=23, minute=0, second=0, microsecond=0)
    mock_trips = [
        MagicMock(
            departure_time_actual=None,
            departure_time_planned=future_time,
            arrival_time="09:00",
        ),
        MagicMock(
            departure_time_actual=None,
            departure_time_planned=future_time + timedelta(minutes=30),
            arrival_time="09:30",
        ),
    ]

    wrapper.get_trips = AsyncMock(return_value=mock_trips)
    return wrapper


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {CONF_API_KEY: "test_api_key"}
    entry.options = {}

    # Mock runtime_data for station caching
    runtime_data = MagicMock()
    runtime_data.stations = [
        MagicMock(code="AMS", name="Amsterdam"),
        MagicMock(code="UTR", name="Utrecht"),
    ]
    runtime_data.stations_updated = datetime.now(UTC).isoformat()
    entry.runtime_data = runtime_data

    # Mock subentries for new route format
    entry.subentries = {}

    return entry


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def coordinator(mock_hass, mock_api_wrapper, mock_config_entry):
    """Create coordinator fixture."""
    return NSDataUpdateCoordinator(mock_hass, mock_api_wrapper, mock_config_entry)


async def test_coordinator_initialization(
    coordinator, mock_api_wrapper, mock_config_entry
) -> None:
    """Test coordinator initialization."""
    assert coordinator.api_wrapper == mock_api_wrapper
    assert coordinator.config_entry == mock_config_entry


async def test_test_connection_success(
    coordinator, mock_hass, mock_api_wrapper
) -> None:
    """Test successful connection test."""

    await coordinator.test_connection()

    mock_api_wrapper.validate_api_key.assert_called_once()


async def test_test_connection_failure(
    coordinator, mock_hass, mock_api_wrapper
) -> None:
    """Test connection test failure."""
    mock_api_wrapper.validate_api_key.side_effect = Exception("Connection failed")

    with pytest.raises(Exception, match="Connection failed"):
        await coordinator.test_connection()


async def test_update_data_no_routes(coordinator, mock_hass, mock_api_wrapper) -> None:
    """Test update data when no routes are configured."""

    result = await coordinator._async_update_data()

    assert result == {"routes": {}}


async def test_update_data_with_routes(
    coordinator, mock_hass, mock_api_wrapper, mock_config_entry
) -> None:
    """Test update data with configured routes."""
    mock_config_entry.options = {
        "routes": [{"name": "Test Route", "from": "AMS", "to": "UTR"}]
    }

    result = await coordinator._async_update_data()

    assert len(result) > 0
    assert "Test Route_AMS_UTR" in result["routes"]
    route_data = result["routes"]["Test Route_AMS_UTR"]
    assert route_data["route"]["name"] == "Test Route"
    assert route_data["route"]["from"] == "AMS"
    assert route_data["route"]["to"] == "UTR"
    assert "trips" in route_data
    assert "first_trip" in route_data
    assert "next_trip" in route_data


async def test_update_data_with_via_route(
    coordinator, mock_hass, mock_api_wrapper, mock_config_entry
) -> None:
    """Test update data with route that has via station."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]

    # Create trips with proper datetime objects
    future_time = datetime.now(UTC) + timedelta(hours=1)
    trips = [
        MagicMock(
            departure_time_actual=future_time, departure_time_planned=future_time
        ),
        MagicMock(
            departure_time_actual=future_time, departure_time_planned=future_time
        ),
    ]

    mock_config_entry.options = {
        "routes": [{"name": "Via Route", "from": "AMS", "to": "UTR", "via": "RTD"}]
    }

    mock_api_wrapper.get_stations.return_value = stations
    mock_api_wrapper.get_trips.return_value = trips

    result = await coordinator._async_update_data()

    assert "Via Route_AMS_UTR_RTD" in result["routes"]
    route_data = result["routes"]["Via Route_AMS_UTR_RTD"]
    assert route_data["route"]["via"] == "RTD"


async def test_update_data_routes_from_data(
    coordinator, mock_hass, mock_api_wrapper, mock_config_entry
) -> None:
    """Test update data gets routes from config entry data when no options."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]

    # Create trips with proper datetime objects
    future_time = datetime.now(UTC) + timedelta(hours=1)
    trips = [
        MagicMock(departure_time_actual=future_time, departure_time_planned=future_time)
    ]

    mock_config_entry.options = {}
    mock_config_entry.data = {
        CONF_API_KEY: "test",
        "routes": [{"name": "Data Route", "from": "AMS", "to": "UTR"}],
    }

    mock_api_wrapper.get_stations.return_value = stations
    mock_api_wrapper.get_trips.return_value = trips

    result = await coordinator._async_update_data()

    assert "Data Route_AMS_UTR" in result["routes"]


async def test_update_data_trip_error_handling(
    coordinator, mock_hass, mock_api_wrapper, mock_config_entry
) -> None:
    """Test update data handles trip fetching errors gracefully."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]

    mock_config_entry.options = {
        "routes": [{"name": "Error Route", "from": "AMS", "to": "UTR"}]
    }

    # Stations call succeeds, trips call fails
    mock_api_wrapper.get_stations.return_value = stations
    mock_api_wrapper.get_trips.side_effect = requests.exceptions.ConnectionError(
        "Network error"
    )

    result = await coordinator._async_update_data()

    assert "Error Route_AMS_UTR" in result["routes"]
    route_data = result["routes"]["Error Route_AMS_UTR"]
    assert route_data["trips"] == []
    assert route_data["first_trip"] is None
    assert route_data["next_trip"] is None


async def test_update_data_api_error(
    coordinator, mock_hass, mock_api_wrapper, mock_config_entry
) -> None:
    """Test update data handles API errors."""
    # Configure routes so API is called
    mock_config_entry.options = {
        "routes": [{"name": "Test Route", "from": "AMS", "to": "UTR"}]
    }

    # Ensure runtime_data has no cached stations or expired cache
    mock_config_entry.runtime_data = None

    mock_api_wrapper.get_stations.side_effect = requests.exceptions.HTTPError(
        "API Error"
    )

    with pytest.raises(UpdateFailed, match="Error communicating with API"):
        await coordinator._async_update_data()


async def test_update_data_parameter_error(
    coordinator, mock_hass, mock_api_wrapper, mock_config_entry
) -> None:
    """Test update data handles parameter errors."""
    # Configure routes so API is called
    mock_config_entry.options = {
        "routes": [{"name": "Test Route", "from": "AMS", "to": "UTR"}]
    }

    # Ensure runtime_data has no cached stations or expired cache
    mock_config_entry.runtime_data = None

    mock_api_wrapper.get_stations.side_effect = RequestParametersError("Invalid params")

    with pytest.raises(UpdateFailed, match="Invalid request parameters"):
        await coordinator._async_update_data()


async def test_get_trips_for_route(coordinator, mock_api_wrapper) -> None:
    """Test getting trips for a route."""
    route = {"from": "AMS", "to": "UTR", "via": "RTD", "time": "08:00", "name": "Test"}
    # Create trips with future offset-aware departure times
    now = datetime.now(UTC) + timedelta(days=1)
    trips = [
        MagicMock(departure_time_actual=now, departure_time_planned=now),
        MagicMock(departure_time_actual=now, departure_time_planned=now),
    ]

    coordinator.config_entry.runtime_data = NSRuntimeData(
        coordinator=coordinator,
        stations=[MagicMock(code="AMS"), MagicMock(code="UTR"), MagicMock(code="RTD")],
    )

    # Mock the async call to get_trips
    async def mock_get_trips(*args, **kwargs):
        return trips

    coordinator.api_wrapper.get_trips = mock_get_trips

    result = await coordinator._get_trips_for_route(route)

    assert result == trips


async def test_get_trips_for_route_no_optional_params(
    coordinator, mock_api_wrapper
) -> None:
    """Test getting trips for a route without optional parameters."""
    route = {"from": "AMS", "to": "UTR", "name": "Test"}
    now = datetime.now(UTC) + timedelta(days=1)
    trips = [MagicMock(departure_time_actual=now, departure_time_planned=now)]

    coordinator.config_entry.runtime_data = NSRuntimeData(
        coordinator=coordinator, stations=[MagicMock(code="AMS"), MagicMock(code="UTR")]
    )

    # Mock the async call to get_trips
    async def mock_get_trips(*args, **kwargs):
        return trips

    coordinator.api_wrapper.get_trips = mock_get_trips

    result = await coordinator._get_trips_for_route(route)

    assert result == trips


async def test_get_trips_for_route_exception(coordinator, mock_api_wrapper) -> None:
    """Test _get_trips_for_route handles exceptions from get_trips."""
    route = {"from": "AMS", "to": "UTR", "name": "Test"}

    # Mock the async call to raise an exception
    async def mock_get_trips(*args, **kwargs):
        raise requests.exceptions.ConnectionError("API error")

    coordinator.api_wrapper.get_trips = mock_get_trips

    result = await coordinator._get_trips_for_route(route)
    assert result == []


async def test_test_connection_empty_stations(
    coordinator, mock_hass, mock_api_wrapper
) -> None:
    """Test test_connection when get_stations returns empty list."""
    mock_api_wrapper.validate_api_key.return_value = None
    await coordinator.test_connection()
    mock_api_wrapper.validate_api_key.assert_called_once()
