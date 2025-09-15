"""Tests for the Smart Meter B-Route sensor."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from momonga import MomongaError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smart_meter_b_route.const import DEFAULT_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_async_setup_entry_with_non_existing_bid(
    hass: HomeAssistant, mock_momonga, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry function."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_smart_meter_b_route_sensor_update(
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


async def test_smart_meter_b_route_sensor_no_update(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the BRouteUpdateCoordinator when failing."""

    entity_id = "sensor.smart_meter_b_route_b_route_id_instantaneous_current_r_phase"
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_momonga.return_value.get_instantaneous_current.side_effect = MomongaError
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity.state is STATE_UNAVAILABLE
