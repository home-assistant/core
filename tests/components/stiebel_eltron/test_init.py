"""Tests for the STIEBEL ELTRON integration."""

from homeassistant.components.stiebel_eltron.const import CONF_HUB, DEFAULT_HUB, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_async_setup_valid_hub(hass: HomeAssistant) -> None:
    """Test async_setup with a valid hub."""
    config = {
        DOMAIN: {
            CONF_NAME: "Stiebel Eltron",
            CONF_HUB: DEFAULT_HUB,
        },
        "modbus": [
            {
                CONF_NAME: DEFAULT_HUB,
                CONF_HOST: "1.1.1.1",
            }
        ],
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_async_setup_with_non_existing_hub(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test async_setup with non-existing modbus hub."""
    config = {
        DOMAIN: {
            CONF_NAME: "Stiebel Eltron",
            CONF_HUB: "non_existing_hub",
        },
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify the issue is created
    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_missing_hub"
    )
    assert issue
    assert issue.active is True
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.translation_key == "deprecated_yaml_import_issue_missing_hub"
    assert issue.severity == ir.IssueSeverity.WARNING
