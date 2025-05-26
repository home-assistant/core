"""Tests for the CUPS sensor platform."""

from unittest.mock import patch

from homeassistant.components.cups import CONF_PRINTERS, DOMAIN as CUPS_DOMAIN
from homeassistant.components.sensor.const import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_repair_issue_is_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issue is created."""
    with patch(
        "homeassistant.components.cups.sensor.CupsData", autospec=True
    ) as cups_data:
        cups_data.available = True
        assert await async_setup_component(
            hass,
            SENSOR_DOMAIN,
            {
                SENSOR_DOMAIN: [
                    {
                        CONF_PLATFORM: CUPS_DOMAIN,
                        CONF_PRINTERS: [
                            "printer1",
                        ],
                    }
                ],
            },
        )
        await hass.async_block_till_done()
        assert (
            HOMEASSISTANT_DOMAIN,
            f"deprecated_system_packages_yaml_integration_{CUPS_DOMAIN}",
        ) in issue_registry.issues
