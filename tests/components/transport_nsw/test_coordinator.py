"""Test the Transport NSW coordinator."""

from unittest.mock import patch

import pytest

from homeassistant.components.transport_nsw.const import DOMAIN
from homeassistant.components.transport_nsw.coordinator import (
    TransportNSWCoordinator,
    _get_value,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_initialization_with_subentry(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test coordinator initialization with subentry."""
    subentry = list(mock_config_entry_with_subentries.subentries.values())[0]

    coordinator = TransportNSWCoordinator(
        hass, mock_config_entry_with_subentries, subentry
    )

    assert coordinator.api_key == "test_api_key"
    assert coordinator.stop_id == "stop_001"
    assert coordinator.route == ""
    assert coordinator.destination == ""
    assert "Central Station" in coordinator.name


async def test_coordinator_initialization_legacy_mode(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test coordinator initialization in legacy mode."""
    coordinator = TransportNSWCoordinator(hass, mock_config_entry_legacy, None)

    assert coordinator.api_key == "test_api_key"
    assert coordinator.stop_id == "test_stop_id"
    assert coordinator.route == ""
    assert coordinator.destination == ""
    assert "Test Stop" in coordinator.name


async def test_coordinator_update_data_success(
    hass: HomeAssistant,
    mock_config_entry_legacy: MockConfigEntry,
    mock_api_response: dict,
) -> None:
    """Test successful data update."""
    coordinator = TransportNSWCoordinator(hass, mock_config_entry_legacy, None)

    with patch.object(
        coordinator.transport_nsw, "get_departures", return_value=mock_api_response
    ):
        data = await coordinator._async_update_data()

    assert data["route"] == "Test Route"
    assert data["due"] == 5
    assert data["delay"] == 0
    assert data["real_time"] is True
    assert data["destination"] == "Test Destination"
    assert data["mode"] == "Bus"


async def test_coordinator_update_data_with_nulls(
    hass: HomeAssistant,
    mock_config_entry_legacy: MockConfigEntry,
    mock_api_response_with_nulls: dict,
) -> None:
    """Test data update with None and n/a values."""
    coordinator = TransportNSWCoordinator(hass, mock_config_entry_legacy, None)

    with patch.object(
        coordinator.transport_nsw,
        "get_departures",
        return_value=mock_api_response_with_nulls,
    ):
        data = await coordinator._async_update_data()

    assert data["route"] is None
    assert data["due"] is None  # "n/a" should become None
    assert data["delay"] == 0
    assert data["real_time"] is True
    assert data["destination"] is None
    assert data["mode"] == "Bus"


async def test_coordinator_update_data_none_response(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test data update with None response from API."""
    coordinator = TransportNSWCoordinator(hass, mock_config_entry_legacy, None)

    with (
        patch.object(coordinator.transport_nsw, "get_departures", return_value=None),
        pytest.raises(UpdateFailed, match="No data returned from Transport NSW API"),
    ):
        await coordinator._async_update_data()


async def test_coordinator_update_data_api_error(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test data update with API error."""
    coordinator = TransportNSWCoordinator(hass, mock_config_entry_legacy, None)

    with (
        patch.object(
            coordinator.transport_nsw,
            "get_departures",
            side_effect=Exception("API Error"),
        ),
        pytest.raises(UpdateFailed, match="Error communicating with Transport NSW API"),
    ):
        await coordinator._async_update_data()


async def test_coordinator_with_subentry_route_filter(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test coordinator with subentry that has route and destination filters."""
    # Get the second subentry which has route and destination filters
    subentry = list(mock_config_entry_with_subentries.subentries.values())[1]

    coordinator = TransportNSWCoordinator(
        hass, mock_config_entry_with_subentries, subentry
    )

    assert coordinator.api_key == "test_api_key"
    assert coordinator.stop_id == "stop_002"
    assert coordinator.route == "T1"
    assert coordinator.destination == "Hornsby"
    assert "Town Hall" in coordinator.name


def test_get_value_helper_function() -> None:
    """Test the _get_value helper function."""
    # Test with None
    assert _get_value(None) is None

    # Test with "n/a"
    assert _get_value("n/a") is None

    # Test with valid values
    assert _get_value("Test") == "Test"
    assert _get_value(5) == 5
    assert _get_value(0) == 0
    assert _get_value(False) is False
    assert _get_value("") == ""


async def test_coordinator_with_options_legacy_mode(hass: HomeAssistant) -> None:
    """Test coordinator with options in legacy mode."""
    # Create a mock entry with options
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test_api_key",
            "stop_id": "test_stop_id",
            CONF_NAME: "Test Stop",
            "route": "",
            "destination": "",
        },
        options={
            "route": "T2",
            "destination": "Parramatta",
        },
        unique_id="test_stop_id",
    )

    coordinator = TransportNSWCoordinator(hass, mock_entry, None)

    assert coordinator.route == "T2"
    assert coordinator.destination == "Parramatta"


async def test_coordinator_update_interval_and_name(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test coordinator update interval and name generation."""
    coordinator = TransportNSWCoordinator(hass, mock_config_entry_legacy, None)

    # Check update interval is set correctly
    assert coordinator.update_interval.total_seconds() == 60

    # Check name generation
    assert "Transport NSW" in coordinator.name
    assert "Test Stop" in coordinator.name


async def test_coordinator_data_processing_edge_cases(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test coordinator data processing with various edge cases."""
    coordinator = TransportNSWCoordinator(hass, mock_config_entry_legacy, None)

    # Test with malformed response (missing keys)
    malformed_response = {"route": "T1"}  # Missing other expected keys

    with patch.object(
        coordinator.transport_nsw, "get_departures", return_value=malformed_response
    ):
        data = await coordinator._async_update_data()

    assert data["route"] == "T1"
    assert data["due"] is None  # Missing key should result in None
    assert data["delay"] is None
    assert data["real_time"] is None
    assert data["destination"] is None
    assert data["mode"] is None


async def test_coordinator_with_empty_subentry_name(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test coordinator with subentry that has empty name."""
    # Create a subentry with empty title
    subentry = ConfigSubentry(
        data={
            "stop_id": "stop_003",
            "name": "",
            "route": "",
            "destination": "",
        },
        subentry_id="subentry_3",
        subentry_type="stop",
        title="",  # Empty title
        unique_id="test_entry_stop_003",
    )

    coordinator = TransportNSWCoordinator(
        hass, mock_config_entry_with_subentries, subentry
    )

    # Should fallback to stop ID in name
    assert "Stop stop_003" in coordinator.name
