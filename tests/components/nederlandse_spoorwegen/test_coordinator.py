"""Test the Nederlandse Spoorwegen coordinator."""

from datetime import UTC, datetime, timedelta
import re
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
def mock_nsapi():
    """Mock NSAPI client."""
    nsapi = MagicMock()
    nsapi.get_stations.return_value = [
        MagicMock(code="AMS", name="Amsterdam"),
        MagicMock(code="UTR", name="Utrecht"),
    ]
    nsapi.get_trips.return_value = [
        MagicMock(departure_time="08:00", arrival_time="09:00"),
        MagicMock(departure_time="08:30", arrival_time="09:30"),
    ]
    return nsapi


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {CONF_API_KEY: "test_api_key"}
    entry.options = {}
    return entry


@pytest.fixture
def mock_hass():
    """Mock Home Assistant."""
    hass = MagicMock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock()
    return hass


@pytest.fixture
def coordinator(mock_hass, mock_nsapi, mock_config_entry):
    """Create coordinator fixture."""
    return NSDataUpdateCoordinator(mock_hass, mock_nsapi, mock_config_entry)


async def test_coordinator_initialization(
    coordinator, mock_nsapi, mock_config_entry
) -> None:
    """Test coordinator initialization."""
    assert coordinator.client == mock_nsapi
    assert coordinator.config_entry == mock_config_entry


async def test_test_connection_success(coordinator, mock_hass, mock_nsapi) -> None:
    """Test successful connection test."""
    mock_hass.async_add_executor_job.return_value = [MagicMock()]

    await coordinator.test_connection()

    mock_hass.async_add_executor_job.assert_called_once_with(mock_nsapi.get_stations)


async def test_test_connection_failure(coordinator, mock_hass, mock_nsapi) -> None:
    """Test connection test failure."""
    mock_hass.async_add_executor_job.side_effect = Exception("Connection failed")

    with pytest.raises(Exception, match="Connection failed"):
        await coordinator.test_connection()


async def test_update_data_no_routes(coordinator, mock_hass, mock_nsapi) -> None:
    """Test update data when no routes are configured."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    mock_hass.async_add_executor_job.return_value = stations

    result = await coordinator._async_update_data()

    assert result == {"routes": {}}


async def test_update_data_with_routes(
    coordinator, mock_hass, mock_nsapi, mock_config_entry
) -> None:
    """Test update data with configured routes."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    trips = [MagicMock(), MagicMock()]

    mock_config_entry.options = {
        "routes": [{"name": "Test Route", "from": "AMS", "to": "UTR"}]
    }

    mock_hass.async_add_executor_job.side_effect = [stations, trips]

    result = await coordinator._async_update_data()

    assert "routes" in result
    assert "Test Route_AMS_UTR" in result["routes"]
    route_data = result["routes"]["Test Route_AMS_UTR"]
    assert route_data["route"]["name"] == "Test Route"
    assert route_data["trips"] == trips
    assert route_data["first_trip"] == trips[0]
    assert route_data["next_trip"] == trips[1]


async def test_update_data_with_via_route(
    coordinator, mock_hass, mock_nsapi, mock_config_entry
) -> None:
    """Test update data with route that has via station."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    trips = [MagicMock()]

    mock_config_entry.options = {
        "routes": [{"name": "Via Route", "from": "AMS", "to": "UTR", "via": "RTD"}]
    }

    mock_hass.async_add_executor_job.side_effect = [stations, trips]

    result = await coordinator._async_update_data()

    assert "Via Route_AMS_UTR_RTD" in result["routes"]
    route_data = result["routes"]["Via Route_AMS_UTR_RTD"]
    assert route_data["route"]["via"] == "RTD"


async def test_update_data_routes_from_data(
    coordinator, mock_hass, mock_nsapi, mock_config_entry
) -> None:
    """Test update data gets routes from config entry data when no options."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]
    trips = [MagicMock()]

    mock_config_entry.options = {}
    mock_config_entry.data = {
        CONF_API_KEY: "test",
        "routes": [{"name": "Data Route", "from": "AMS", "to": "UTR"}],
    }

    mock_hass.async_add_executor_job.side_effect = [stations, trips]

    result = await coordinator._async_update_data()

    assert "Data Route_AMS_UTR" in result["routes"]


async def test_update_data_trip_error_handling(
    coordinator, mock_hass, mock_nsapi, mock_config_entry
) -> None:
    """Test update data handles trip fetching errors gracefully."""
    stations = [MagicMock(code="AMS"), MagicMock(code="UTR")]

    mock_config_entry.options = {
        "routes": [{"name": "Error Route", "from": "AMS", "to": "UTR"}]
    }

    # First call for stations succeeds, second call for trips fails
    mock_hass.async_add_executor_job.side_effect = [
        stations,
        requests.exceptions.ConnectionError("Network error"),
    ]

    result = await coordinator._async_update_data()

    assert "Error Route_AMS_UTR" in result["routes"]
    route_data = result["routes"]["Error Route_AMS_UTR"]
    assert route_data["trips"] == []
    assert route_data["first_trip"] is None
    assert route_data["next_trip"] is None


async def test_update_data_api_error(coordinator, mock_hass, mock_nsapi) -> None:
    """Test update data handles API errors."""
    mock_hass.async_add_executor_job.side_effect = requests.exceptions.HTTPError(
        "API Error"
    )

    with pytest.raises(UpdateFailed, match="Error communicating with API"):
        await coordinator._async_update_data()


async def test_update_data_parameter_error(coordinator, mock_hass, mock_nsapi) -> None:
    """Test update data handles parameter errors."""
    mock_hass.async_add_executor_job.side_effect = RequestParametersError(
        "Invalid params"
    )

    with pytest.raises(UpdateFailed, match="Invalid request parameters"):
        await coordinator._async_update_data()


async def test_get_trips_for_route(coordinator, mock_nsapi) -> None:
    """Test getting trips for a route."""
    route = {"from": "AMS", "to": "UTR", "via": "RTD", "time": "08:00", "name": "Test"}
    # Create trips with future offset-aware departure times
    now = datetime.now(UTC) + timedelta(days=1)
    trips = [
        MagicMock(departure_time_actual=now, departure_time_planned=now),
        MagicMock(departure_time_actual=now, departure_time_planned=now),
    ]
    mock_nsapi.get_trips.return_value = trips

    coordinator.config_entry.runtime_data = NSRuntimeData(
        coordinator=coordinator,
        stations=[MagicMock(code="AMS"), MagicMock(code="UTR"), MagicMock(code="RTD")],
    )

    result = coordinator._get_trips_for_route(route)

    assert result == trips
    assert mock_nsapi.get_trips.call_count == 1
    args = mock_nsapi.get_trips.call_args.args
    # The first argument is the trip time string (e.g., '10-07-2025 08:00')
    assert re.match(r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}", args[0])
    assert args[1] == "AMS"
    assert args[2] == "RTD"
    assert args[3] == "UTR"


async def test_get_trips_for_route_no_optional_params(coordinator, mock_nsapi) -> None:
    """Test getting trips for a route without optional parameters."""
    route = {"from": "AMS", "to": "UTR", "name": "Test"}
    now = datetime.now(UTC) + timedelta(days=1)
    trips = [MagicMock(departure_time_actual=now, departure_time_planned=now)]
    mock_nsapi.get_trips.return_value = trips

    coordinator.config_entry.runtime_data = NSRuntimeData(
        coordinator=coordinator, stations=[MagicMock(code="AMS"), MagicMock(code="UTR")]
    )

    result = coordinator._get_trips_for_route(route)

    assert result == trips
    assert mock_nsapi.get_trips.call_count == 1
    args = mock_nsapi.get_trips.call_args.args
    # The first argument is the trip time string (e.g., '10-07-2025 15:48')
    assert re.match(r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}", args[0])
    assert args[1] == "AMS"
    assert args[2] is None
    assert args[3] == "UTR"


async def test_get_trips_for_route_exception(coordinator, mock_nsapi) -> None:
    """Test _get_trips_for_route handles exceptions from get_trips."""
    route = {"from": "AMS", "to": "UTR", "name": "Test"}
    mock_nsapi.get_trips.side_effect = Exception("API error")
    result = coordinator._get_trips_for_route(route)
    assert result == []


async def test_test_connection_empty_stations(
    coordinator, mock_hass, mock_nsapi
) -> None:
    """Test test_connection when get_stations returns empty list."""
    mock_hass.async_add_executor_job.return_value = []
    await coordinator.test_connection()
    mock_hass.async_add_executor_job.assert_called_once_with(mock_nsapi.get_stations)
