"""Tests for the removed Telegram notify platform."""

from homeassistant.components import notify
from homeassistant.components.telegram.notify import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_integration_removed_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a YAML notify configuration raises the integration removed issue."""
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {notify.DOMAIN: [{"platform": DOMAIN, "name": DOMAIN, "chat_id": 1}]},
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, DOMAIN)
    assert issue is not None
    assert issue.translation_key == "integration_removed"
    assert issue.severity is ir.IssueSeverity.ERROR
    assert not hass.services.has_service(notify.DOMAIN, DOMAIN)
