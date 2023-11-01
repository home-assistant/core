"""Tests for the Hydrawise integration."""

from unittest.mock import Mock

from requests.exceptions import HTTPError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_import_success(hass: HomeAssistant, mock_pydrawise: Mock) -> None:
    """Test that setup with a YAML config triggers an import and warning."""
    mock_pydrawise.update_controller_info.return_value = True
    mock_pydrawise.customer_id = 12345
    mock_pydrawise.status = "unknown"
    config = {"hydrawise": {CONF_ACCESS_TOKEN: "_access-token_"}}
    assert await async_setup_component(hass, "hydrawise", config)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_hydrawise"
    )
    assert issue.translation_key == "deprecated_yaml"


async def test_connect_retry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pydrawise: Mock
) -> None:
    """Test that a connection error triggers a retry."""
    mock_pydrawise.update_controller_info.side_effect = HTTPError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_no_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_pydrawise: Mock
) -> None:
    """Test that no data from the API triggers a retry."""
    mock_pydrawise.update_controller_info.return_value = False
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
