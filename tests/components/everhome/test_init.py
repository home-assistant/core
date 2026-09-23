"""Tests for the everHome/EcoTracker integration."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.common import MockConfigEntry


async def test_connection_failed(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the device is unreachable."""
    mock_everhome_client.async_update.return_value = False
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
