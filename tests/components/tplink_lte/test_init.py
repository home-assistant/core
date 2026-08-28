"""Tests for the TP-Link LTE integration."""

from homeassistant.components.tplink_lte import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_tplink_lte_repair_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the TP-Link LTE repair issue is created on setup."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: [{"host": "192.168.0.1", "password": "secret"}]},
    )
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, DOMAIN)
    issue = issue_registry.async_get_issue(DOMAIN, DOMAIN)
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_key == "integration_removed"
