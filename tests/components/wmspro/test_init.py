"""Test the wmspro initialization."""

from unittest.mock import AsyncMock

import aiohttp

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_config_entry

from tests.common import MockConfigEntry


async def test_config_entry_device_config_ping_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
) -> None:
    """Test that a config entry will be retried due to ConfigEntryNotReady."""
    mock_hub_ping.side_effect = aiohttp.ClientError
    await setup_config_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert len(mock_hub_ping.mock_calls) == 1


async def test_config_entry_device_config_refresh_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_refresh: AsyncMock,
) -> None:
    """Test that a config entry will be retried due to ConfigEntryNotReady."""
    mock_hub_refresh.side_effect = aiohttp.ClientError
    await setup_config_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_refresh.mock_calls) == 1
