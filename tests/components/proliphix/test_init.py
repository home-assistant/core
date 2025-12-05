"""Test the Proliphix integration initialization."""

from unittest.mock import MagicMock

import pytest
import requests

from homeassistant.components.proliphix.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_proliphix")


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    # Test setup
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Test unload
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_proliphix: MagicMock,
) -> None:
    """Test config entry setup with connection error."""
    mock_config_entry.add_to_hass(hass)

    # Mock connection error during setup
    mock_proliphix.update.side_effect = requests.exceptions.ConnectionError(
        "Connection failed"
    )

    # Setup should fail
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_proliphix")
async def test_setup_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test setting up Proliphix via YAML configuration."""
    config = {
        "climate": {
            "platform": "proliphix",
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password123",
        }
    }

    # Setup the integration with YAML config
    assert await async_setup_component(hass, "climate", config)
    await hass.async_block_till_done()

    # Check that repair issue was created for deprecated YAML configuration
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == "deprecated_yaml"

    # Wait for the import flow to complete
    await hass.async_block_till_done()

    # Check that a config entry was created via import
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].source == "import"
    assert config_entries[0].data == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password123",
    }
