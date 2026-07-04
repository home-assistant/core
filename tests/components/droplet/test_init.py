"""Test Droplet initialization."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_no_version_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator setup where Droplet never sends version info."""
    mock_droplet.version_info_available.return_value = False
    await setup_integration(hass, mock_config_entry)

    assert "Failed to get version info from Droplet" in caplog.text


async def test_setup_droplet_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
) -> None:
    """Test integration setup when Droplet is offline."""
    mock_droplet.connected = False
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
