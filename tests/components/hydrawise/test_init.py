"""Tests for the Hydrawise integration."""

from unittest.mock import AsyncMock

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_connect_retry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pydrawise: AsyncMock
) -> None:
    """Test that a connection error triggers a retry."""
    mock_pydrawise.get_user.side_effect = ClientError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_version(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test updating to the GaphQL API works."""
    mock_config_entry_legacy.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_legacy.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry_legacy.state is ConfigEntryState.SETUP_ERROR

    # Make sure reauth flow has been initiated
    assert any(mock_config_entry_legacy.async_get_active_flows(hass, {"reauth"}))
