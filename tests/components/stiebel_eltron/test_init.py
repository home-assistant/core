"""Tests for the STIEBEL ELTRON integration."""

from homeassistant.components.stiebel_eltron import _async_import
from homeassistant.components.stiebel_eltron.const import CONF_HUB, DEFAULT_HUB, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


async def test_async_import(hass: HomeAssistant) -> None:
    """Test _async_import."""
    config = {
        DOMAIN: {
            CONF_NAME: "Stiebel Eltron",
            CONF_HUB: "non_existing_hub",
        },
        "modbus": [
            {
                CONF_NAME: DEFAULT_HUB,
                CONF_HOST: "1.1.1.1",
            }
        ],
    }

    await _async_import(hass, config)
    issues = hass.data["issue_registry"].issues
    assert len(issues) == 1
    issue = issues[(DOMAIN, "deprecated_yaml_import_issue_missing_hub")]
    assert issue.translation_key == "deprecated_yaml_import_issue_missing_hub"
    assert issue.severity == ir.IssueSeverity.WARNING
