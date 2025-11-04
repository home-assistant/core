"""Test the Rejseplanen base entity."""

from unittest.mock import MagicMock, patch

from py_rejseplan.dataclasses.departure import DepartureType

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_integration_setup_with_stop(
    setup_integration_with_stop: tuple[MockConfigEntry, MockConfigEntry],
) -> None:
    """Test integration sets up successfully with stop."""
    main_entry, _ = setup_integration_with_stop

    # Verify main entry is loaded
    assert main_entry.state.name == "LOADED"


async def test_coordinator_manages_stop_ids(
    hass: HomeAssistant,
    setup_integration_with_stop: tuple[MockConfigEntry, MockConfigEntry],
) -> None:
    """Test coordinator properly manages stop IDs from subentries."""
    main_entry, _ = setup_integration_with_stop

    coordinator = main_entry.runtime_data

    # Coordinator should exist
    assert coordinator is not None

    # Check that coordinator has methods for managing stops
    assert hasattr(coordinator, "add_stop_id")
    assert hasattr(coordinator, "remove_stop_id")


async def test_coordinator_data_update(
    hass: HomeAssistant,
    setup_integration_with_stop: tuple[MockConfigEntry, MockConfigEntry],
    mock_departure_data: list[DepartureType],
) -> None:
    """Test coordinator updates data successfully."""
    main_entry, _ = setup_integration_with_stop

    coordinator = main_entry.runtime_data

    # Initial data should be available
    assert coordinator.last_update_success is True or coordinator.data is not None

    # Trigger manual refresh with new data
    with patch.object(
        coordinator.api,
        "get_departures",
        return_value=(MagicMock(departures=mock_departure_data), []),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate successful update
    assert coordinator.last_update_success is True


async def test_coordinator_handles_api_error(
    hass: HomeAssistant,
    setup_integration_with_stop: tuple[MockConfigEntry, MockConfigEntry],
) -> None:
    """Test coordinator handles API errors gracefully."""
    main_entry, _ = setup_integration_with_stop

    coordinator = main_entry.runtime_data

    # Simulate API error
    with patch.object(
        coordinator.api, "get_departures", side_effect=Exception("API Error")
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Coordinator should indicate update failure
    assert not coordinator.last_update_success


async def test_coordinator_stop_management(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator add/remove stop functionality."""
    coordinator = init_integration.runtime_data

    # Test adding stops
    coordinator.add_stop_id(123456)
    coordinator.add_stop_id(789012)

    # Verify stops are registered
    assert 123456 in coordinator._stop_ids
    assert 789012 in coordinator._stop_ids

    # Test removing stop
    coordinator.remove_stop_id(123456)
    assert 123456 not in coordinator._stop_ids
    assert 789012 in coordinator._stop_ids
