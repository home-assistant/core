"""Decora component tests."""

from unittest.mock import Mock, patch

from homeassistant.components.decora import DOMAIN as DECORA_DOMAIN
from homeassistant.components.light import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


@patch.dict("sys.modules", {"bluepy": Mock(), "bluepy.btle": Mock(), "decora": Mock()})
async def test_repair_issue_is_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issue is created."""
    assert await async_setup_component(
        hass,
        PLATFORM_DOMAIN,
        {
            PLATFORM_DOMAIN: [
                {
                    CONF_PLATFORM: DECORA_DOMAIN,
                }
            ],
        },
    )
    await hass.async_block_till_done()
    assert (
        HOMEASSISTANT_DOMAIN,
        f"deprecated_system_packages_yaml_integration_{DECORA_DOMAIN}",
    ) in issue_registry.issues
