"""Tests for init of Azure DevOps."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: MagicMock,
) -> None:
    """Test a successful setup entry."""
    assert await setup_integration(hass, mock_config_entry)

    assert mock_devops_client.authorized
    assert mock_devops_client.authorize.call_count == 1
    assert mock_devops_client.get_builds.call_count == 2

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: AsyncMock,
) -> None:
    """Test a failed setup entry."""
    mock_devops_client.authorize.return_value = False
    mock_devops_client.authorized = False

    await setup_integration(hass, mock_config_entry)

    assert not mock_devops_client.authorized

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: MagicMock,
) -> None:
    """Test a failed update entry."""
    mock_devops_client.get_builds.side_effect = aiohttp.ClientError

    await setup_integration(hass, mock_config_entry)

    assert mock_devops_client.get_builds.call_count == 1

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_no_builds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: MagicMock,
) -> None:
    """Test a failed update entry."""
    mock_devops_client.get_builds.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_devops_client.get_builds.call_count == 1

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
