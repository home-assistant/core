"""Tests for the coordinator of the TechnoVE integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from technove import TechnoVEConnectionError, TechnoVEError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_connection_error(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator update connection error."""
    mock_technove.update.side_effect = TechnoVEConnectionError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_failure(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update failure."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[mock_config_entry.domain][mock_config_entry.entry_id]
    assert coordinator.last_update_success is True

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    mock_technove.update.side_effect = TechnoVEError("Test error")
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert isinstance(coordinator.last_exception, UpdateFailed) is True
