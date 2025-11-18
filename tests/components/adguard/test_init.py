"""Tests for the AdGuard Home."""

from unittest.mock import patch

from adguardhome import AdGuardHomeConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard setup."""
    with patch("homeassistant.components.adguard.PLATFORMS", []):
        await setup_integration(hass, mock_config_entry, aioclient_mock)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard setup failed."""
    mock_config_entry.add_to_hass(hass)

    aioclient_mock.get(
        "https://127.0.0.1:3000/control/status",
        exc=AdGuardHomeConnectionError("Connection error"),
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
