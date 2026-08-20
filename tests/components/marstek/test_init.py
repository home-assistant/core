"""Tests for the Marstek integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.marstek.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import create_mock_udp_client

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up a config entry."""
    mock_config_entry.add_to_hass(hass)
    mock_client = create_mock_udp_client()

    # Mock the UDP client in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["udp_client"] = mock_client

    with patch.object(
        hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
    ) as mock_forward_entry_setups:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is mock_client
    mock_client.get_device_info.assert_awaited_once()
    mock_forward_entry_setups.assert_awaited_once()


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when the device cannot be reached."""
    mock_config_entry.add_to_hass(hass)
    mock_client = create_mock_udp_client()
    mock_client.get_device_info.side_effect = TimeoutError("timeout")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["udp_client"] = mock_client

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
