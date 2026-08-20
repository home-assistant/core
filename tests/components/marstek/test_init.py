"""Tests for the Marstek integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setting up a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
    ) as mock_forward_entry_setups:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is mock_udp_client
    mock_udp_client.get_device_info.assert_awaited_once()
    mock_forward_entry_setups.assert_awaited_once()


async def test_async_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_client: MagicMock,
) -> None:
    """Test setup retries when the device cannot be reached."""
    mock_config_entry.add_to_hass(hass)
    mock_udp_client.get_device_info.side_effect = TimeoutError("timeout")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
