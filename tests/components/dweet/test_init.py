"""Test for dweet component."""

from homeassistant.components.dweet import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_setup_platform_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test platform setup starts repair issue."""

    config = {
        SENSOR_DOMAIN: {"platform": "dweet"},
    }

    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, DOMAIN)


async def test_setup_component_repair_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test component setup starts repair issue."""

    config = {}

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, DOMAIN)
