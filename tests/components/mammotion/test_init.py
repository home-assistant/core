"""Tests for the Mammotion integration setup."""

from unittest.mock import MagicMock, Mock

from aiohttp import ClientConnectorError
from Tea.exceptions import UnretryableException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import DEFAULT_NAME

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_mower_api.mammotion.stop.assert_awaited_once()
    mock_mower_api.mammotion.remove_device.assert_awaited_once_with(DEFAULT_NAME)


async def test_setup_retry_on_failed_refresh(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the first data fetch fails."""
    mock_mower_api.update.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry is retried when the cloud is unreachable."""
    mock_mower_api.mammotion.login_and_initiate_cloud.side_effect = (
        ClientConnectorError(Mock(), OSError("boom"))
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_error_on_unretryable_error(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry errors out on an unretryable login failure."""
    mock_mower_api.mammotion.login_and_initiate_cloud.side_effect = (
        UnretryableException(Mock(), OSError("boom"))
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
