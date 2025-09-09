"""Tests for eddystone temperature."""

from unittest.mock import Mock, patch

from homeassistant.components.eddystone_temperature import (
    CONF_BEACONS,
    CONF_INSTANCE,
    CONF_NAMESPACE,
    DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


@patch.dict("sys.modules", beacontools=Mock())
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
                    CONF_PLATFORM: DOMAIN,
                    CONF_BEACONS: {
                        "living_room": {
                            CONF_NAMESPACE: "112233445566778899AA",
                            CONF_INSTANCE: "000000000001",
                        }
                    },
                }
            ],
        },
    )
    await hass.async_block_till_done()
    assert (
        HOMEASSISTANT_DOMAIN,
        f"deprecated_system_packages_yaml_integration_{DOMAIN}",
    ) in issue_registry.issues
