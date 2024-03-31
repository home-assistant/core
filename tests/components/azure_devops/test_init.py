"""Tests for init of Azure DevOps."""

from unittest.mock import MagicMock

import aiohttp

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_init(
    hass: HomeAssistant,
    mock_devops_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test a successful setup entry."""
    assert mock_devops_client.authorized
    assert mock_devops_client.authorize.call_count == 1
    assert mock_devops_client.get_builds.call_count == 2

    assert init_integration.state == ConfigEntryState.LOADED


async def test_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: MagicMock,
) -> None:
    """Test a failed setup entry."""
    mock_devops_client.authorize.return_value = False
    mock_devops_client.authorized = False

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_devops_client.authorized

    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: MagicMock,
) -> None:
    """Test a failed update entry."""
    mock_devops_client.get_builds.side_effect = aiohttp.ClientError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_devops_client.get_builds.call_count == 1

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_no_builds(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_devops_client: MagicMock,
) -> None:
    """Test a failed update entry."""
    mock_devops_client.get_builds.return_value = None

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_devops_client.get_builds.called

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY
