"""Tests for the IPP integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyipp import IPPConnectionError

from homeassistant.components.ipp.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@patch(
    "homeassistant.components.ipp.coordinator.IPP._request",
    side_effect=IPPConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the IPP configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ipp: AsyncMock,
) -> None:
    """Test the IPP configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
