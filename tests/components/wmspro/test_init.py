"""Test the wmspro initialization."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_entry_device_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_refresh: AsyncMock,
) -> None:
    """Test that a config entry can be loaded with DeviceConfig."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_refresh.mock_calls) == 1
