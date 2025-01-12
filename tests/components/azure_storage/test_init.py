"""Test the Azure storage integration."""

from unittest.mock import MagicMock

from homeassistant.components.azure_storage.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_container_does_not_exist(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the storage container does not exist."""
    mock_client.exists.return_value = False
    await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(DOMAIN, "container_not_found")
    assert issue
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
