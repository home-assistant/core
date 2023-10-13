"""Tests for the Hydrawise integration."""

from unittest.mock import Mock

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component


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
