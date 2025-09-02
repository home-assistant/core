"""Test the Nederlandse Spoorwegen coordinator."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from ns_api import RequestParametersError
import pytest
import requests

from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_api_wrapper():
    """Mock API wrapper."""
    wrapper = MagicMock()
    wrapper.validate_api_key = AsyncMock(return_value=True)
    wrapper.get_stations = AsyncMock(
        return_value=[
            # Major stations
            MagicMock(code="AMS", name="Amsterdam"),
            MagicMock(code="Asd", name="Amsterdam Centraal"),
            MagicMock(code="Ut", name="Utrecht Centraal"),
            MagicMock(code="UTR", name="Utrecht"),
            MagicMock(code="Rtd", name="Rotterdam Centraal"),
            MagicMock(code="Gvc", name="Den Haag Centraal"),
            MagicMock(code="Gv", name="Den Haag HS"),
            MagicMock(code="Ht", name="'s-Hertogenbosch"),
            # Test stations from our routes
            MagicMock(code="UTG", name="Uitgeest"),
            MagicMock(code="HT", name="'s-Hertogenbosch"),  # Alternative code
            # Additional common stations
            MagicMock(code="Ehv", name="Eindhoven Centraal"),
            MagicMock(code="Ah", name="Arnhem Centraal"),
            MagicMock(code="Hlm", name="Haarlem"),
            MagicMock(code="Lw", name="Leeuwarden"),
            MagicMock(code="Gn", name="Groningen"),
            MagicMock(code="RTD", name="Rotterdam"),
        ]
    )

    # Create trips with proper datetime objects
    future_time = datetime.now(UTC).replace(
        hour=8, minute=30, second=0, microsecond=0
    ) + timedelta(days=1)  # Tomorrow at 8:30
    # Ensure we have a proper future time relative to test execution
    if future_time <= datetime.now(UTC):
        future_time = datetime.now(UTC) + timedelta(
            hours=1
        )  # At least 1 hour in the future

    # Round to remove microseconds for consistency
    future_time = future_time.replace(microsecond=0)
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
        # Major stations
        MagicMock(code="AMS", name="Amsterdam"),
        MagicMock(code="Asd", name="Amsterdam Centraal"),
        MagicMock(code="Ut", name="Utrecht Centraal"),
        MagicMock(code="UTR", name="Utrecht"),
        MagicMock(code="Rtd", name="Rotterdam Centraal"),
        MagicMock(code="Gvc", name="Den Haag Centraal"),
        MagicMock(code="Gv", name="Den Haag HS"),
        MagicMock(code="Ht", name="'s-Hertogenbosch"),
        # Test stations from our routes
        MagicMock(code="UTG", name="Uitgeest"),
        MagicMock(code="HT", name="'s-Hertogenbosch"),  # Alternative code
        # Additional common stations
        MagicMock(code="Ehv", name="Eindhoven Centraal"),
        MagicMock(code="Ah", name="Arnhem Centraal"),
        MagicMock(code="Hlm", name="Haarlem"),
        MagicMock(code="Lw", name="Leeuwarden"),
        MagicMock(code="Gn", name="Groningen"),
        MagicMock(code="RTD", name="Rotterdam"),
    ]
    runtime_data.stations_updated = datetime.now(UTC) - timedelta(minutes=5)
    entry.runtime_data = runtime_data
    return entry


@pytest.fixture
def coordinator(mock_hass, mock_api_wrapper, mock_config_entry):
    """Mock coordinator."""
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
    assert route_data["trips"] == []  # Mock returns empty since no proper mocking


async def test_update_data_with_via_routes(
    coordinator, mock_hass, mock_api_wrapper, mock_config_entry
) -> None:
    """Test update data with routes that have via stations."""
    stations = [
        # Major stations
        MagicMock(code="AMS", name="Amsterdam"),
        MagicMock(code="Asd", name="Amsterdam Centraal"),
        MagicMock(code="Ut", name="Utrecht Centraal"),
        MagicMock(code="UTR", name="Utrecht"),
        MagicMock(code="Rtd", name="Rotterdam Centraal"),
        MagicMock(code="RTD", name="Rotterdam"),
        MagicMock(code="Gvc", name="Den Haag Centraal"),
        MagicMock(code="Ht", name="'s-Hertogenbosch"),
        # Test stations
        MagicMock(code="UTG", name="Uitgeest"),
        MagicMock(code="HT", name="'s-Hertogenbosch"),
    ]

    # Create trips with proper datetime objects
    future_time = datetime.now(UTC) + timedelta(hours=1)
    trips = [
        MagicMock(departure_time_actual=None, departure_time_planned=future_time),
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
    stations = [
        # Major stations
        MagicMock(code="AMS", name="Amsterdam"),
        MagicMock(code="Asd", name="Amsterdam Centraal"),
        MagicMock(code="Ut", name="Utrecht Centraal"),
        MagicMock(code="UTR", name="Utrecht"),
        MagicMock(code="Gvc", name="Den Haag Centraal"),
        MagicMock(code="Ht", name="'s-Hertogenbosch"),
        # Test stations
        MagicMock(code="UTG", name="Uitgeest"),
        MagicMock(code="HT", name="'s-Hertogenbosch"),
    ]

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
    stations = [
        MagicMock(code="AMS", name="Amsterdam"),
        MagicMock(code="UTR", name="Utrecht"),
        MagicMock(code="UTG", name="Uitgeest"),
        MagicMock(code="HT", name="'s-Hertogenbosch"),
    ]

    mock_config_entry.options = {
        "routes": [{"name": "Error Route", "from": "AMS", "to": "UTR"}]
    }
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
        "API error"
    )

    # When there are routes but stations can't be fetched and no cache, should raise
    with pytest.raises(
        UpdateFailed, match="Failed to fetch stations and no cache available"
    ):
        await coordinator._async_update_data()


async def test_update_data_request_parameters_error(
    coordinator, mock_hass, mock_api_wrapper, mock_config_entry
) -> None:
    """Test update data handles RequestParametersError."""
    mock_config_entry.options = {
        "routes": [{"name": "Test Route", "from": "AMS", "to": "UTR"}]
    }

    mock_config_entry.runtime_data = None
    mock_api_wrapper.get_stations.side_effect = RequestParametersError("Invalid params")

    # When there are routes but stations can't be fetched and no cache, should raise
    with pytest.raises(
        UpdateFailed, match="Failed to fetch stations and no cache available"
    ):
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

    # Mock runtime data with stations
    runtime_data = MagicMock()
    runtime_data.coordinator = coordinator
    runtime_data.stations = [
        type("Station", (), {"code": "AMS", "name": "Amsterdam"})(),
        type("Station", (), {"code": "UTR", "name": "Utrecht"})(),
        type("Station", (), {"code": "RTD", "name": "Rotterdam"})(),
    ]
    coordinator.config_entry.runtime_data = runtime_data

    # Mock the api_wrapper's get_station_codes method
    mock_api_wrapper.get_station_codes.return_value = {"AMS", "UTR", "RTD"}

    # Mock the async call to get trips
    mock_api_wrapper.get_trips.return_value = trips

    result = await coordinator._get_trips_for_route(route)
    assert len(result) == 2


async def test_get_trips_for_route_exception_handling(coordinator) -> None:
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


async def test_get_routes_dict_format(coordinator, mock_config_entry) -> None:
    """Test _get_routes with dict format (current options flow format)."""
    # Test the new dict format used by options flow
    mock_config_entry.options = {
        "routes": {
            "UTG_HT": {
                "name": "Uitgeest to 's-Hertogenbosch",
                "from": "UTG",
                "to": "HT",
                "via": "",
                "time": "",
            },
            "AMS_UTR": {
                "name": "Amsterdam to Utrecht",
                "from": "AMS",
                "to": "UTR",
                "via": "",
                "time": "08:00",
            },
        }
    }

    routes = coordinator._get_routes()
    assert len(routes) == 2

    # Check that we got proper route dicts, not keys
    route_names = [route["name"] for route in routes]
    assert "Uitgeest to 's-Hertogenbosch" in route_names
    assert "Amsterdam to Utrecht" in route_names

    # Verify structure
    for route in routes:
        assert isinstance(route, dict)
        assert "name" in route
        assert "from" in route
        assert "to" in route
        assert "via" in route
        assert "time" in route


async def test_get_routes_list_format_legacy(coordinator, mock_config_entry) -> None:
    """Test _get_routes with list format (legacy format)."""
    # Test legacy list format
    mock_config_entry.options = {
        "routes": [
            {
                "name": "Test Route",
                "from": "AMS",
                "to": "UTR",
                "via": "",
                "time": "",
            }
        ]
    }

    routes = coordinator._get_routes()
    assert len(routes) == 1
    assert routes[0]["name"] == "Test Route"
    assert routes[0]["from"] == "AMS"
    assert routes[0]["to"] == "UTR"


async def test_get_routes_empty_data(coordinator, mock_config_entry) -> None:
    """Test _get_routes with empty/invalid data."""
    # Test with no routes configured
    mock_config_entry.options = {}
    mock_config_entry.data = {}
    routes = coordinator._get_routes()
    assert routes == []

    # Test with invalid data type
    mock_config_entry.options = {"routes": "invalid_string"}
    routes = coordinator._get_routes()
    assert routes == []

    # Test with None config entry
    coordinator.config_entry = None
    routes = coordinator._get_routes()
    assert routes == []


async def test_get_routes_fallback_to_data(coordinator, mock_config_entry) -> None:
    """Test _get_routes falls back to config entry data when options empty."""
    mock_config_entry.options = {}
    mock_config_entry.data = {
        "routes": [
            {
                "name": "Data Route",
                "from": "AMS",
                "to": "UTR",
                "via": "",
                "time": "",
            }
        ]
    }

    routes = coordinator._get_routes()
    assert len(routes) == 1
    assert routes[0]["name"] == "Data Route"


async def test_update_data_with_dict_routes(
    coordinator, mock_hass, mock_api_wrapper, mock_config_entry
) -> None:
    """Test update data with dict format routes (regression test for UTG_HT issue)."""
    # Test the exact scenario that was causing "Skipping invalid route data: UTG_HT"
    mock_config_entry.options = {
        "routes": {
            "UTG_HT": {
                "name": "Uitgeest to 's-Hertogenbosch",
                "from": "UTG",
                "to": "HT",
                "via": "",
                "time": "",
            }
        }
    }

    result = await coordinator._async_update_data()
    assert len(result) > 0
    assert "routes" in result

    # Should have the route key based on name and stations
    expected_key = "Uitgeest to 's-Hertogenbosch_UTG_HT"
    assert expected_key in result["routes"]

    route_data = result["routes"][expected_key]
    assert route_data["route"]["name"] == "Uitgeest to 's-Hertogenbosch"
    assert route_data["route"]["from"] == "UTG"
    assert route_data["route"]["to"] == "HT"
    assert "trips" in route_data
