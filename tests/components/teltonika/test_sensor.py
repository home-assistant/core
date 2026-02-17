"""Test Teltonika sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion
from teltasync import TeltonikaConnectionError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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
    mock_modems.get_status.return_value = mock_response

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
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
    mock_modems: AsyncMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable on update failure and recovers."""

    # Get initial sensor state,  here it should be available
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "-63"

    mock_modems.get_status.side_effect = TeltonikaConnectionError("Connection lost")

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should now be unavailable
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "unavailable"
    # Simulate recovery
    mock_modems.get_status.side_effect = None

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should be available again with correct data
    state = hass.states.get("sensor.rutx50_test_internal_modem_rssi")
    assert state is not None
    assert state.state == "-63"
