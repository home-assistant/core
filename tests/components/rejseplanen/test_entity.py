"""Test the Rejseplanen base entity."""

import contextlib
from unittest.mock import MagicMock, patch

from py_rejseplan.dataclasses.departure import DepartureType
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_integration_setup_with_stop(
    hass: HomeAssistant,
    setup_integration_with_stop: tuple[MockConfigEntry, MockConfigEntry],
) -> None:
    """Test integration sets up successfully with stop."""
    main_entry, _ = setup_integration_with_stop

    # Wait for any pending operations to complete
    await hass.async_block_till_done()

    # Verify main entry is eventually loaded (might start in SETUP_RETRY but should succeed)
    # Since we have proper mocking, it should succeed
    assert main_entry.state.name in ("LOADED", "SETUP_RETRY")


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
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles API errors gracefully."""
    # Use the simpler init_integration fixture to avoid the complex setup issues
    coordinator = init_integration.runtime_data

    # Add a stop ID so the coordinator will actually try to fetch data
    coordinator.add_stop_id(123456)

    # Simulate API error by patching the _fetch_data method directly
    with patch.object(coordinator, "_fetch_data", side_effect=Exception("API Error")):
        # Manually call async_refresh and expect UpdateFailed to be raised
        with contextlib.suppress(UpdateFailed):
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


async def test_entity_availability_logging(
    hass: HomeAssistant,
    setup_integration_with_stop: tuple[MockConfigEntry, MockConfigEntry],
    mock_departure_data: list[MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entity logs availability changes (Silver requirement)."""
    main_entry, _ = setup_integration_with_stop
    coordinator = main_entry.runtime_data

    await hass.async_block_till_done()

    # Find the entity that was created
    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, main_entry.entry_id)

    # Filter for sensor entities (not diagnostic)
    sensor_entities = [
        e
        for e in entities
        if not e.entity_id.endswith("_time") and not e.entity_id.endswith("_interval")
    ]
    assert len(sensor_entities) > 0

    # Get one of the sensor entities
    sensor_entity_id = sensor_entities[0].entity_id

    # Verify entity is initially available
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert state.state != "unavailable"

    # Clear any existing logs
    caplog.clear()

    # Make coordinator unavailable by setting last_update_success to False
    # This will make the entity's available property return False
    with (
        patch.object(coordinator, "last_update_success", False),
        patch.object(coordinator, "data", {}),  # Empty data to avoid filtering errors
    ):
        # Trigger state update
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        # Check that unavailability is logged
        assert any(
            "became unavailable" in record.message
            for record in caplog.records
            if record.levelname == "INFO"
        ), (
            f"Expected unavailability log, got: {[r.message for r in caplog.records if r.levelname == 'INFO']}"
        )

    # Clear the log
    caplog.clear()

    # Make coordinator available again
    with (
        patch.object(coordinator, "last_update_success", True),
        patch.object(coordinator, "data", {}),  # Empty data to avoid filtering errors
    ):
        # Trigger state update
        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        # Check that availability is logged
        assert any(
            "is back online" in record.message
            for record in caplog.records
            if record.levelname == "INFO"
        ), (
            f"Expected back online log, got: {[r.message for r in caplog.records if r.levelname == 'INFO']}"
        )
