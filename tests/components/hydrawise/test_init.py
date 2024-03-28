"""Tests for the Hydrawise integration."""

from unittest.mock import AsyncMock

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_import_success(
    hass: HomeAssistant, mock_legacy_pydrawise: AsyncMock
) -> None:
    """Test that setup with a YAML config triggers an import and warning."""
    config = {"hydrawise": {CONF_ACCESS_TOKEN: "_access-token_"}}
    assert await async_setup_component(hass, "hydrawise", config)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_hydrawise"
    )
    assert issue.translation_key == "deprecated_yaml"


async def test_connect_retry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pydrawise: AsyncMock
) -> None:
    """Test that a connection error triggers a retry."""
    mock_pydrawise.get_user.side_effect = ClientError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_version(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test updating to the GaphQL API works."""
    mock_config_entry_legacy.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_legacy.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry_legacy.state is ConfigEntryState.SETUP_ERROR

    # Make sure reauth flow has been initiated
    assert any(mock_config_entry_legacy.async_get_active_flows(hass, {"reauth"}))
