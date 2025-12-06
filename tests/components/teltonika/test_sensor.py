"""Test Teltonika sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teltasync_init: MagicMock,
    mock_modems: MagicMock,
) -> MockConfigEntry:
    """Set up the Teltonika integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test sensor entities match snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_sensor_modem_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_modems: MagicMock,
) -> None:
    """Test sensor becomes unavailable when modem is removed."""
    # Get initial sensor state - entity starts as unknown because it hasn't processed initial data yet
    state = hass.states.get("sensor.test_device_internal_modem_rssi")
    assert state is not None

    # Update coordinator with empty modem data
    mock_response = MagicMock()
    mock_response.data = []  # No modems
    mock_modems.return_value.get_status.return_value = mock_response

    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check that entity is marked as unavailable
    state = hass.states.get("sensor.test_device_internal_modem_rssi")
    assert state is not None
    # When modem is removed, entity should be marked unavailable
    # Verify through entity registry that entity exists but is unavailable
    entity_entry = entity_registry.async_get("sensor.test_device_internal_modem_rssi")
    assert entity_entry is not None
    # State should show unavailable when modem is removed
    assert state.state == "unavailable"
