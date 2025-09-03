"""Test Droplet coordinator."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.droplet.coordinator import DropletDataCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test Droplet coordinator successful setup."""
    coordinator = DropletDataCoordinator(hass, mock_config_entry)
    assert await coordinator.setup()
    assert "Failed to get version info from Droplet" not in caplog.text


async def test_setup_droplet_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
) -> None:
    """Test coordinator setup when Droplet is offline."""
    coordinator = DropletDataCoordinator(hass, mock_config_entry)

    attrs = {
        "connected": False,
    }
    mock_droplet.configure_mock(**attrs)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator._async_setup()


async def test_setup_no_version_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator setup where Droplet never sends version info."""
    coordinator = DropletDataCoordinator(hass, mock_config_entry)

    attrs = {
        "version_info_available.return_value": False,
    }
    mock_droplet.configure_mock(**attrs)

    await coordinator._async_setup()
    assert "Failed to get version info from Droplet" in caplog.text
