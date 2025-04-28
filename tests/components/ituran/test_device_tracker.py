"""Test the Ituran device_tracker."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyituran.exceptions import IturanApiError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ituran.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_device_tracker(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_ituran: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state of device_tracker."""
    with patch("homeassistant.components.ituran.PLATFORMS", [Platform.DEVICE_TRACKER]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_ituran: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device is marked as unavailable when we can't reach the Ituran service."""
    entity_id = "device_tracker.mock_model"
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    mock_ituran.get_vehicles.side_effect = IturanApiError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_ituran.get_vehicles.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
