"""Tests for the AdGuard Home."""

from unittest.mock import AsyncMock, patch

from adguardhome import AdGuardHomeConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard setup."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, mock_adguard)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard setup failed."""
    mock_adguard.version.side_effect = AdGuardHomeConnectionError("Connection error")

    await setup_integration(hass, mock_config_entry, mock_adguard)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
