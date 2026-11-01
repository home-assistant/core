"""Tests for the removed Zengge light platform."""

import logging

import pytest

from homeassistant.components import light
from homeassistant.components.zengge.light import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_integration_removed_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML light configuration raises the integration removed issue."""
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: [{"platform": DOMAIN}]}
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, DOMAIN)
    assert issue is not None
    assert issue.translation_key == "integration_removed"
    assert issue.severity is ir.IssueSeverity.ERROR
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
