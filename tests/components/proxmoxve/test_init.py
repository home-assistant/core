"""Tests for the Proxmox VE integration initialization."""

from unittest.mock import MagicMock

from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import pytest
import requests
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.proxmoxve.const import (
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry


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


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (
            AuthenticationError("Invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            SSLError("SSL handshake failed"),
            ConfigEntryState.SETUP_ERROR,
        ),
        (ConnectTimeout("Connection timed out"), ConfigEntryState.SETUP_RETRY),
        (
            ResourceException(500, "Internal Server Error", ""),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            requests.exceptions.ConnectionError("Connection refused"),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
    ids=[
        "auth_error",
        "ssl_error",
        "connect_timeout",
        "resource_exception",
        "connection_error",
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the _async_setup."""
    mock_proxmox_client.nodes.get.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == expected_state


async def test_migration_v1_to_v2(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test migration from version 1 to 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id="1",
        data={
            CONF_HOST: "http://test_host",
            CONF_PORT: 8006,
            CONF_REALM: "pam",
            CONF_USERNAME: "test_user@pam",
            CONF_PASSWORD: "test_password",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)
    assert entry.version == 1

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    vm_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_vm_100")},
        name="Test VM",
    )

    container_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_container_200")},
        name="Test Container",
    )

    vm_entity = entity_registry.async_get_or_create(
        domain="binary_sensor",
        platform=DOMAIN,
        unique_id="proxmox_pve1_100_running",
        config_entry=entry,
        device_id=vm_device.id,
        original_name="Test VM Binary Sensor",
    )

    container_entity = entity_registry.async_get_or_create(
        domain="binary_sensor",
        platform=DOMAIN,
        unique_id="proxmox_pve1_200_running",
        config_entry=entry,
        device_id=container_device.id,
        original_name="Test Container Binary Sensor",
    )

    assert vm_entity.unique_id == "proxmox_pve1_100_running"
    assert container_entity.unique_id == "proxmox_pve1_200_running"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2

    vm_entity_after = entity_registry.async_get(vm_entity.entity_id)
    container_entity_after = entity_registry.async_get(container_entity.entity_id)

    assert vm_entity_after.unique_id == f"{entry.entry_id}_100_status"
    assert container_entity_after.unique_id == f"{entry.entry_id}_200_status"
