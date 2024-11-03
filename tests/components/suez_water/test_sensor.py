"""Test Suez_water sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.suez_water.const import DATA_REFRESH_INTERVAL
from homeassistant.components.suez_water.coordinator import PySuezError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors_valid_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    suez_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that suez_water sensor is loaded and in a valid state."""
    with patch("homeassistant.components.suez_water.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_failed_update(
    hass: HomeAssistant,
    suez_client,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that suez_water sensor reflect failure when api fails."""

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    entity_ids = await hass.async_add_executor_job(hass.states.entity_ids)
    assert len(entity_ids) == 1

    state = hass.states.get(entity_ids[0])
    assert entity_ids[0]
    assert state.state != STATE_UNAVAILABLE

    suez_client.update.side_effect = PySuezError("Should fail to update")

    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(True)

    state = hass.states.get(entity_ids[0])
    assert state
    assert state.state == STATE_UNAVAILABLE
