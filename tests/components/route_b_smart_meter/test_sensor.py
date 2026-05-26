"""Tests for the Smart Meter B-Route sensor."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from momonga import MomongaError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.route_b_smart_meter.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_route_b_smart_meter_sensor_update(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the BRouteUpdateCoordinator successful behavior."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_route_b_smart_meter_sensor_no_update(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the BRouteUpdateCoordinator when failing."""

    entity_id = (
        "sensor.route_b_smart_meter_"
        "01234567890123456789012345f789_"
        "instantaneous_current_r_phase"
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == "1"

    mock_momonga.return_value.get_instantaneous_current.side_effect = MomongaError
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity.state is STATE_UNAVAILABLE


async def test_recovery_reopen_session(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test recovery when session is closed."""
    entity_id = (
        "sensor.route_b_smart_meter_"
        "01234567890123456789012345f789_"
        "instantaneous_current_r_phase"
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initial state
    assert hass.states.get(entity_id).state == "1"

    # Simulate session closed error on next update
    client = mock_momonga.return_value
    client.get_instantaneous_current.side_effect = [
        RuntimeError("session not open"),
        {"r phase current": 10, "t phase current": 20},
    ]

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify api.open() was called and data was updated
    assert client.open.call_count == 2  # Once in setup, once in recovery
    assert hass.states.get(entity_id).state == "10"


async def test_recovery_force_close_on_failure(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test serial port is closed on failure."""
    entity_id = (
        "sensor.route_b_smart_meter_"
        "01234567890123456789012345f789_"
        "instantaneous_current_r_phase"
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.get_instantaneous_current.side_effect = MomongaError("Poll failed")

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify state is unavailable and api.close() was called
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    client.close.assert_called_once()


async def test_recovery_unhandled_runtime_error(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a generic RuntimeError is not swallowed."""
    entity_id = (
        "sensor.route_b_smart_meter_"
        "01234567890123456789012345f789_"
        "instantaneous_current_r_phase"
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.get_instantaneous_current.side_effect = RuntimeError("Unknown error")

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_recovery_close_fails(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test recovery when api.close() also fails."""
    entity_id = (
        "sensor.route_b_smart_meter_"
        "01234567890123456789012345f789_"
        "instantaneous_current_r_phase"
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = mock_momonga.return_value
    client.get_instantaneous_current.side_effect = MomongaError("Primary failure")
    client.close.side_effect = Exception("Emergency close failed")

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify state is still unavailable even if cleanup fails
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    client.close.assert_called_once()
