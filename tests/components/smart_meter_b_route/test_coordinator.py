"""Tests for the Smart Meter B Route Coordinator."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from momonga import MomongaError
from syrupy import SnapshotAssertion

from homeassistant.components.smart_meter_b_route.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import configure_integration

from tests.common import async_fire_time_changed, snapshot_platform


async def test_broute_update_coordinator(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the BRouteUpdateCoordinator successful behavior."""
    config_entry = configure_integration(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_broute_fails_to_update_coordinator(
    hass: HomeAssistant,
    mock_momonga: Mock,
    freezer: FrozenDateTimeFactory,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the BRouteUpdateCoordinator when failing."""

    entity_id = "sensor.smart_meter_b_route_b_route_id_instantaneous_current_r_phase"
    config_entry = configure_integration(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_momonga.return_value.get_instantaneous_current.side_effect = MomongaError
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity.state is STATE_UNAVAILABLE
