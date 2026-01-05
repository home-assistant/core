"""Tests for the STIEBEL ELTRON integration."""

from homeassistant.components.stiebel_eltron.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_async_setup_success(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test successful async_setup."""
    config = {}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    # No issue should be created by the new async_setup
    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")
    assert issue is None
