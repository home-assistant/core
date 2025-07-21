"""Test coordinator edge cases and error handling."""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_station_cache_expiry(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test station cache expiry logic."""
    # Create a mock config entry
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )
    config_entry.runtime_data = MagicMock()

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Test cache validation with expired timestamp
    expired_time = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    assert not coordinator._is_station_cache_valid(expired_time)

    # Test cache validation with valid timestamp
    valid_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert coordinator._is_station_cache_valid(valid_time)

    # Test cache validation with invalid timestamp
    assert not coordinator._is_station_cache_valid("invalid-timestamp")
    assert not coordinator._is_station_cache_valid(None)


async def test_coordinator_refresh_station_cache_error_handling(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test station cache refresh error handling."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )
    config_entry.runtime_data = MagicMock()

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Test API error during refresh
    mock_ns_api_wrapper.get_stations.side_effect = requests.ConnectionError("API down")

    with pytest.raises(requests.ConnectionError):
        await coordinator._refresh_station_cache()

    # Verify unavailability logging
    assert coordinator._unavailable_logged


async def test_coordinator_route_key_generation(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test route key generation logic."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Test with route_id
    route_with_id = {"route_id": "test_route_123", "name": "Test"}
    assert coordinator._generate_route_key(route_with_id) == "test_route_123"

    # Test without route_id but with required fields
    route_without_id = {
        "name": "Amsterdam-Utrecht",
        "from": "AMS",
        "to": "UT",
        "via": "ASS",
    }
    expected_key = "Amsterdam-Utrecht_AMS_UT_ASS"
    assert coordinator._generate_route_key(route_without_id) == expected_key

    # Test without via station
    route_no_via = {"name": "Test", "from": "AMS", "to": "UT"}
    assert coordinator._generate_route_key(route_no_via) == "Test_AMS_UT"

    # Test missing required fields
    invalid_route = {"name": "Test", "from": "AMS"}  # Missing 'to'
    assert coordinator._generate_route_key(invalid_route) is None


async def test_coordinator_route_validation(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test route structure validation."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Test valid route structure
    valid_route = {"name": "Test", "from": "AMS", "to": "UT"}
    assert coordinator._validate_route_structure(valid_route)

    # Test invalid route structure
    invalid_route = {"name": "Test", "from": "AMS"}  # Missing 'to'
    assert not coordinator._validate_route_structure(invalid_route)

    # Test non-dict route (use Any type to bypass type checking)
    invalid_str: Any = "invalid"
    assert not coordinator._validate_route_structure(invalid_str)

    invalid_none: Any = None
    assert not coordinator._validate_route_structure(invalid_none)


async def test_coordinator_station_validation(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test station validation logic."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )

    # Mock runtime data with stations
    config_entry.runtime_data = MagicMock()
    config_entry.runtime_data.stations = [
        {"code": "AMS", "names": {"medium": "Amsterdam Centraal"}},
        {"code": "UT", "names": {"medium": "Utrecht Centraal"}},
    ]

    # Mock the get_station_codes method to return codes from test data
    mock_ns_api_wrapper.get_station_codes.return_value = {"AMS", "UT"}

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Test valid stations
    valid_route = {"from": "AMS", "to": "UT"}
    assert coordinator._validate_route_stations(valid_route)

    # Test invalid from station
    invalid_from = {"from": "INVALID", "to": "UT"}
    assert not coordinator._validate_route_stations(invalid_from)

    # Test invalid to station
    invalid_to = {"from": "AMS", "to": "INVALID"}
    assert not coordinator._validate_route_stations(invalid_to)

    # Test invalid via station
    invalid_via = {"from": "AMS", "to": "UT", "via": "INVALID"}
    assert not coordinator._validate_route_stations(invalid_via)


async def test_coordinator_time_parsing(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test time parsing and validation."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Test valid time formats
    time_hhmm = coordinator._build_trip_time("14:30")
    assert time_hhmm.hour == 14
    assert time_hhmm.minute == 30

    time_hhmmss = coordinator._build_trip_time("14:30:45")
    assert time_hhmmss.hour == 14
    assert time_hhmmss.minute == 30

    # Test invalid time format
    time_invalid = coordinator._build_trip_time("invalid")
    # Should fallback to current time
    assert isinstance(time_invalid, datetime)

    # Test empty time
    time_empty = coordinator._build_trip_time("")
    assert isinstance(time_empty, datetime)


async def test_coordinator_api_error_recovery(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test API error recovery and logging."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )
    config_entry.runtime_data = MagicMock()

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Simulate API failure then recovery
    mock_ns_api_wrapper.get_stations.side_effect = [
        requests.ConnectionError("API down"),
        [{"code": "AMS", "names": {"medium": "Amsterdam"}}],
    ]

    # First call should fail and set unavailable flag
    with pytest.raises(requests.ConnectionError):
        await coordinator._refresh_station_cache()
    assert coordinator._unavailable_logged

    # Second call should succeed and reset flag
    mock_ns_api_wrapper.get_stations.side_effect = None
    mock_ns_api_wrapper.get_stations.return_value = [
        {"code": "AMS", "names": {"medium": "Amsterdam"}}
    ]
    await coordinator._refresh_station_cache()
    # Note: flag reset is tested in _async_update_data


async def test_coordinator_fetch_route_data_error_handling(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test route data fetching with various error conditions."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Test with invalid route data
    routes = [
        "invalid_route",  # Not a dict
        {"name": "invalid"},  # Missing required fields
        {"name": "valid", "from": "AMS", "to": "UT"},  # Valid route
    ]

    # Mock _get_trips_for_route to return test data
    with patch.object(coordinator, "_get_trips_for_route") as mock_get_trips:
        mock_get_trips.return_value = [MagicMock()]

        route_data = await coordinator._fetch_route_data(routes)

        # Should only have data for the valid route
        assert len(route_data) == 1
        assert "valid_AMS_UT" in route_data


async def test_coordinator_legacy_routes_fallback(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test fallback to legacy routes format."""
    # Create config entry with legacy routes in options
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
        options={"routes": [{"name": "Legacy", "from": "AMS", "to": "UT"}]},
    )

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    routes = coordinator._get_routes()
    assert len(routes) == 1
    assert routes[0]["name"] == "Legacy"


async def test_coordinator_update_data_no_stations_error(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test update data when stations cannot be fetched."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        options={"routes": [{"name": "Test", "from": "AMS", "to": "UT"}]},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Mock _ensure_stations_available to return None
    with (
        patch.object(coordinator, "_ensure_stations_available", return_value=None),
        pytest.raises(UpdateFailed, match="Failed to fetch stations"),
    ):
        await coordinator._async_update_data()


async def test_coordinator_cached_stations_error_handling(
    hass: HomeAssistant,
    mock_ns_api_wrapper: AsyncMock,
) -> None:
    """Test cached stations access with various error conditions."""
    config_entry = MockConfigEntry(
        domain="nederlandse_spoorwegen",
        data={"api_key": "test_key"},
        title="Nederlandse Spoorwegen",
        unique_id="nederlandse_spoorwegen",
    )

    coordinator = NSDataUpdateCoordinator(hass, mock_ns_api_wrapper, config_entry)

    # Test with no runtime_data
    config_entry.runtime_data = None
    stations, updated = coordinator._get_cached_stations()
    assert stations is None
    assert updated is None

    # Test with valid runtime_data but missing attributes
    config_entry.runtime_data = MagicMock()
    config_entry.runtime_data.stations = None
    config_entry.runtime_data.stations_updated = None

    stations, updated = coordinator._get_cached_stations()
    assert stations is None
    assert updated is None
