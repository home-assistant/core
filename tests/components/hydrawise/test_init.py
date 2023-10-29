"""Tests for the Hydrawise integration."""

from unittest.mock import Mock, patch

from requests.exceptions import HTTPError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_import_success(hass: HomeAssistant, mock_pydrawise: Mock) -> None:
    """Test that setup with a YAML config triggers an import and warning."""
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
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a connection error triggers a retry."""
    with patch("pydrawise.legacy.LegacyHydrawise") as mock_api:
        mock_api.side_effect = HTTPError
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        mock_api.assert_called_once()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_no_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that no data from the API triggers a retry."""
    with patch("pydrawise.legacy.LegacyHydrawise") as mock_api:
        mock_api.return_value.controller_info = {}
        mock_api.return_value.controller_status = None
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        mock_api.assert_called_once()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
