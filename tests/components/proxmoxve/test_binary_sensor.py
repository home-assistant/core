"""Test the Proxmox VE binary sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
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
    CONF_PLATFORM,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
import homeassistant.helpers.entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_config_import(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_setup_entry: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test sensor initialization."""
    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await async_setup_component(
            hass,
            BINARY_SENSOR_DOMAIN,
            {
                BINARY_SENSOR_DOMAIN: [
                    {
                        CONF_PLATFORM: DOMAIN,
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
