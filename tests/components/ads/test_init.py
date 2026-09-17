"""Test the ADS integration setup."""

from unittest.mock import MagicMock

import pyads
import pytest

from homeassistant.components.ads.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import AMS_NET_ID

from tests.common import MockConfigEntry

YAML_CONFIG = {
    DOMAIN: {
        CONF_DEVICE: AMS_NET_ID,
        CONF_IP_ADDRESS: "192.168.1.10",
        CONF_PORT: 851,
    }
}


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test setting up and unloading the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_pyads_connection.open.assert_called_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_pyads_connection.close.assert_called_once()


async def test_setup_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test the entry is retried when the device is unreachable."""
    mock_pyads_connection.read_state.side_effect = pyads.ADSError(text="timeout")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_pyads_connection.close.assert_called_once()


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_yaml_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test YAML is imported and a deprecation issue is raised."""
    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the deprecation issue is raised when an entry already exists."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_failed(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a failed import raises an integration issue."""
    mock_pyads_connection.read_state.side_effect = pyads.ADSError(text="timeout")

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
