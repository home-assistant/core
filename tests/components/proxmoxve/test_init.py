"""Tests for the Proxmox VE integration initialization."""

from unittest.mock import MagicMock

from homeassistant.components.proxmoxve.const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_config_import(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_setup_entry: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test sensor initialization."""
    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    CONF_HOST: "127.0.0.1",
                    CONF_PORT: 8006,
                    CONF_REALM: "pam",
                    CONF_USERNAME: "test_user@pam",
                    CONF_PASSWORD: "test_password",
                    CONF_VERIFY_SSL: True,
                    CONF_NODES: [
                        {
                            CONF_NODE: "pve1",
                            CONF_VMS: [100, 101],
                            CONF_CONTAINERS: [200, 201],
                        },
                    ],
                }
            ]
        },
    )

    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    assert (HOMEASSISTANT_DOMAIN, "deprecated_yaml") in issue_registry.issues
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
