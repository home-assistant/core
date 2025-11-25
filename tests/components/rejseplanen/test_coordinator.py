# tests/components/rejseplanen/test_coordinator.py
"""Test the Rejseplanen coordinator."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from py_rejseplan.exceptions import (
    APIError,
    ConnectionError as RejseplanConnectionError,
)
from requests.exceptions import HTTPError

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def test_coordinator_successful_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator successful data update."""
    mock_config_entry.add_to_hass(hass)

    # Mock successful API response
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_departures.return_value = (
            MagicMock(departures=[{"line": "A", "direction": "North"}]),
            [],
        )
        mock_api_class.return_value = mock_api

        # Setup integration - this triggers first refresh
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify coordinator was created and has data
    assert mock_config_entry.runtime_data is not None
    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_update_success is True


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles API errors during refresh."""
    coordinator = init_integration.runtime_data

    # Mock API failure for the coordinator's update
    with patch.object(coordinator, "_fetch_data", side_effect=Exception("API Error")):
        # Trigger a refresh that should fail
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate update failure
    assert not coordinator.last_update_success


async def test_coordinator_add_remove_stop_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator stop ID management."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_departures.return_value = (MagicMock(departures=[]), [])
        mock_api_class.return_value = mock_api

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # Test adding stop IDs
    coordinator.add_stop_id(12345)
    coordinator.add_stop_id(67890)

    assert 12345 in coordinator._stop_ids
    assert 67890 in coordinator._stop_ids

    # Test removing stop ID
    coordinator.remove_stop_id(12345)
    assert 12345 not in coordinator._stop_ids
    assert 67890 in coordinator._stop_ids


async def test_coordinator_auth_failed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles authentication failures during refresh."""
    coordinator = init_integration.runtime_data

    # Mock auth failure during coordinator update
    with patch.object(
        coordinator, "_fetch_data", side_effect=HTTPError("401 Unauthorized")
    ):
        # Trigger a refresh that should fail with auth error
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate update failure
    assert not coordinator.last_update_success


async def test_coordinator_api_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles APIError exceptions."""
    coordinator = init_integration.runtime_data

    # Mock APIError from the library
    with patch.object(
        coordinator, "_fetch_data", side_effect=APIError("API rate limit exceeded")
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate update failure
    assert not coordinator.last_update_success


async def test_coordinator_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles ConnectionError exceptions."""
    coordinator = init_integration.runtime_data

    # Mock ConnectionError from the library
    with patch.object(
        coordinator,
        "_fetch_data",
        side_effect=RejseplanConnectionError("Network timeout"),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate update failure
    assert not coordinator.last_update_success


async def test_coordinator_type_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles TypeError exceptions."""
    coordinator = init_integration.runtime_data

    # Mock TypeError (e.g., unexpected data format from API)
    with patch.object(
        coordinator, "_fetch_data", side_effect=TypeError("Unexpected data type")
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate update failure
    assert not coordinator.last_update_success


async def test_coordinator_generic_exception(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles unexpected generic exceptions."""
    coordinator = init_integration.runtime_data

    # Mock a generic unexpected exception
    with patch.object(
        coordinator, "_fetch_data", side_effect=RuntimeError("Unexpected error")
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate update failure
    assert not coordinator.last_update_success


async def test_coordinator_available_property(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator available property."""
    coordinator = init_integration.runtime_data

    # After successful initialization, coordinator should be available
    assert coordinator.available is True
    assert coordinator.last_update_success_time is not None
    assert coordinator.update_interval is not None

    # Simulate an update within 3x the interval (should still be available)
    recent_time = dt_util.now() - 2 * coordinator.update_interval
    coordinator.last_update_success_time = recent_time
    assert coordinator.available is True

    # Simulate an old update (beyond 3x update interval)
    old_time = dt_util.now() - 3 * coordinator.update_interval - timedelta(minutes=1)
    coordinator.last_update_success_time = old_time

    # Coordinator should now be unavailable (update too old)
    assert coordinator.available is False

    # Trigger a successful refresh to make it available again
    with patch.object(
        coordinator, "_fetch_data", return_value=MagicMock(departures=[])
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Should be available again
    assert coordinator.available is True


async def test_coordinator_get_filtered_departures_with_type_filter(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator filters departures by departure type."""
    coordinator = init_integration.runtime_data

    # Create mock departures with dynamic date and time based on now
    base_dt = dt_util.now().replace(microsecond=0) + timedelta(minutes=15)
    base_date = base_dt.strftime("%Y-%m-%d")

    mock_bus = MagicMock()
    mock_bus.stopExtId = 123456
    mock_bus.direction = "North"
    mock_bus.date = base_date
    mock_bus.time = (base_dt + timedelta(minutes=0)).strftime("%H:%M:%S")
    mock_bus.rtDate = None
    mock_bus.rtTime = None
    mock_bus.product.cls_id = 1  # Bus type

    mock_train = MagicMock()
    mock_train.stopExtId = 123456
    mock_train.direction = "North"
    mock_train.date = base_date
    mock_train.time = (base_dt + timedelta(minutes=5)).strftime("%H:%M:%S")
    mock_train.rtDate = None
    mock_train.rtTime = None
    mock_train.product.cls_id = 2  # Train type

    mock_metro = MagicMock()
    mock_metro.stopExtId = 123456
    mock_metro.direction = "North"
    mock_metro.date = base_date
    mock_metro.time = (base_dt + timedelta(minutes=10)).strftime("%H:%M:%S")
    mock_metro.rtDate = None
    mock_metro.rtTime = None
    mock_metro.product.cls_id = 4  # Metro type

    # Set coordinator data with all three departures
    mock_board = MagicMock()
    mock_board.departures = [
        mock_bus,
        mock_train,
        mock_metro,
    ]
    coordinator.data = mock_board

    # Test filtering with departure_type_filter (bitflag for buses: 1)
    filtered = coordinator.get_filtered_departures(
        stop_id=123456,
        departure_type_filter=1,  # Only buses
    )

    # Should only return the bus departure
    assert len(filtered) == 1
    assert filtered[0].product.cls_id == 1

    # Test filtering with departure_type_filter (bitflag for trains: 2)
    filtered = coordinator.get_filtered_departures(
        stop_id=123456,
        departure_type_filter=2,  # Only trains
    )

    # Should only return the train departure
    assert len(filtered) == 1
    assert filtered[0].product.cls_id == 2

    # Test filtering with combined bitflag (buses and metros: 1 | 4 = 5)
    filtered = coordinator.get_filtered_departures(
        stop_id=123456,
        departure_type_filter=5,  # Buses and metros
    )

    # Should return bus and metro departures
    assert len(filtered) == 2
    assert any(d.product.cls_id == 1 for d in filtered)
    assert any(d.product.cls_id == 4 for d in filtered)
