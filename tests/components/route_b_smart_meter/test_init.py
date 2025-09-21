"""Tests for the Smart Meter B Route integration init."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_momonga, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done()


async def test_async_setup_entry_route_b_id_mismatch(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails when Route B ID doesn't match."""
    with patch("momonga.Momonga") as mock_momonga:
        client = mock_momonga.return_value
        client.__enter__.return_value = client
        client.__exit__.return_value = None
        # Mock a different Route B ID than what's in config
        client.get_route_b_id.return_value = {
            "manufacturer code": b"TEST",
            "authentication id": "DIFFERENT_ROUTE_B_ID",
        }

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
