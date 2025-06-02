"""Tests for the LIRC."""

from unittest.mock import Mock, patch

from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


@patch.dict("sys.modules", lirc=Mock())
async def test_repair_issue_is_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issue is created."""
    from homeassistant.components.lirc import (  # pylint: disable=import-outside-toplevel
        DOMAIN as LIRC_DOMAIN,
    )

    assert await async_setup_component(
        hass,
        LIRC_DOMAIN,
        {
            LIRC_DOMAIN: {},
        },
    )
    await hass.async_block_till_done()
    assert (
        HOMEASSISTANT_DOMAIN,
        f"deprecated_system_packages_yaml_integration_{LIRC_DOMAIN}",
    ) in issue_registry.issues
