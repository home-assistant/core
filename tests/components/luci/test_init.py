"""Tests for the luci integration."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.luci.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

YAML_CONFIG = {
    DEVICE_TRACKER_DOMAIN: {
        CONF_PLATFORM: DOMAIN,
        CONF_HOST: "192.168.1.1",
        CONF_USERNAME: "root",
        CONF_PASSWORD: "password",
    }
}


@pytest.mark.usefixtures("mock_luci_client")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
) -> None:
    """Test setup fails with ConfigEntryNotReady on connection error."""
    mock_luci_client.is_logged_in.side_effect = RequestsConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luci_client: MagicMock,
) -> None:
    """Test setup fails with ConfigEntryAuthFailed and starts a reauth flow."""
    mock_luci_client.is_logged_in.return_value = False

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_yaml_import_invalid_auth(
    hass: HomeAssistant,
    mock_luci_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing YAML config creates an issue on invalid auth."""
    mock_luci_client.is_logged_in.return_value = False

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_invalid_auth")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.1.1"}


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_yaml_import_cannot_connect(
    hass: HomeAssistant,
    mock_luci_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test importing YAML config creates an issue on connection failure."""
    mock_luci_client.is_logged_in.side_effect = RequestsConnectionError

    assert await async_setup_component(hass, DEVICE_TRACKER_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "yaml_import_cannot_connect")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {"host": "192.168.1.1"}
