"""Tests for the Indevolt integration initialization and services."""

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_unload(
    hass: HomeAssistant, mock_indevolt, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and removing a config entry."""
    await setup_integration(hass, mock_config_entry)

    # Verify the config entry is successfully loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Unload the integration
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry is properly unloaded
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("generation", [2], indirect=True)
async def test_load_failure(
    hass: HomeAssistant, mock_indevolt, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure when coordinator update fails."""
    # Simulate timeout error during coordinator update
    mock_indevolt.fetch_data.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the config entry enters retry state due to failure
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
