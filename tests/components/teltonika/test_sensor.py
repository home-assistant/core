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


async def test_sensor_band_attributes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_modems: MagicMock,
) -> None:
    """Test sensor attributes including band fallback."""
    # Update modem with sc_band_av attribute
    mock_modem = MagicMock()
    mock_modem.id = "2-1"
    mock_modem.name = "Internal modem"
    mock_modem.conntype = "4G"
    mock_modem.operator = "test.operator"
    mock_modem.state = "connected"
    mock_modem.rssi = -75
    mock_modem.rsrp = -100
    mock_modem.rsrq = -10
    mock_modem.sinr = 10
    mock_modem.temperature = 45
    mock_modem.sc_band_av = "B3"  # Preferred band attribute
    mock_modem.band = "B1"  # Fallback band

    mock_response = MagicMock()
    mock_response.data = [mock_modem]
    mock_modems.return_value.get_status.return_value = mock_response
    mock_modems.is_online.return_value = True

    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check signal strength sensor has sc_band_av
    state = hass.states.get("sensor.test_device_internal_modem_rssi")
    assert state is not None
    assert state.attributes["band"] == "B3"

    # Now test fallback to band when sc_band_av is None
    mock_modem.sc_band_av = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_device_internal_modem_rssi")
    assert state is not None
    assert state.attributes["band"] == "B1"
