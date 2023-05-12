"""Test Axis component setup process."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components import axis
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry(hass: HomeAssistant, setup_config_entry) -> None:
    """Test successful setup of entry."""
    assert setup_config_entry.state == ConfigEntryState.LOADED


async def test_setup_entry_fails(hass: HomeAssistant, config_entry) -> None:
    """Test successful setup of entry."""
    mock_device = Mock()
    mock_device.async_setup = AsyncMock(return_value=False)

    with patch.object(axis, "AxisNetworkDevice") as mock_device_class:
        mock_device_class.return_value = mock_device

        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant, setup_config_entry) -> None:
    """Test successful unload of entry."""
    assert setup_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(setup_config_entry.entry_id)
    assert setup_config_entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("config_entry_version", [1])
async def test_migrate_entry(hass: HomeAssistant, config_entry) -> None:
    """Test successful migration of entry data."""
    assert config_entry.version == 1

    mock_device = Mock()
    mock_device.async_setup = AsyncMock()
    mock_device.async_update_device_registry = AsyncMock()
    mock_device.api.vapix.light_control = None
    mock_device.api.vapix.params.image_format = None

    with patch("homeassistant.components.axis.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state == ConfigEntryState.LOADED
    assert config_entry.version == 3
