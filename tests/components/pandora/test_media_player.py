"""Pandora media player tests."""

from homeassistant.components.media_player import DOMAIN as PLATFORM_DOMAIN
from homeassistant.components.pandora import DOMAIN as PANDORA_DOMAIN
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


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
                    CONF_PLATFORM: PANDORA_DOMAIN,
                }
            ],
        },
    )
    await hass.async_block_till_done()
    assert (
        HOMEASSISTANT_DOMAIN,
        f"deprecated_system_packages_yaml_integration_{PANDORA_DOMAIN}",
    ) in issue_registry.issues
