"""Test Teltonika sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion
from teltasync import TeltonikaConnectionError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable when modem is removed."""

    # Get initial sensor state
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None

    # Update coordinator with empty modem data
    mock_response = MagicMock()
    mock_response.data = []  # No modems
    mock_modems.return_value.get_status.return_value = mock_response

    coordinator = init_integration.runtime_data.coordinator

    freezer.tick(timedelta(seconds=31))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Check that entity is marked as unavailable
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None

    # When modem is removed, entity should be marked as unavailable
    # Verify through entity registry that entity exists but is unavailable
    entity_entry = entity_registry.async_get("sensor.rutx50_test_internal_modem_rssi")
    assert entity_entry is not None
    # State should show unavailable when modem is removed
    assert state.state == "unavailable"


async def test_sensor_update_failure_and_recovery(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_modems: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable on update failure and recovers."""

    # Get initial sensor state,  here it should be available
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "-63"

    coordinator = init_integration.runtime_data.coordinator

    # Save the original get_status mock before we replace it
    original_get_status = mock_modems.return_value.get_status

    # Simulate coordinator update failure by replacing get_status with error
    mock_modems.return_value.get_status = AsyncMock(
        side_effect=TeltonikaConnectionError("Connection lost")
    )

    freezer.tick(timedelta(seconds=31))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Sensor should now be unavailable
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"
    # Simulate recovery
    mock_modems.return_value.get_status = original_get_status

    freezer.tick(timedelta(seconds=31))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Sensor should be available again with correct data
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "-63"
