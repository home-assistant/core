"""Tests for the Proxmox VE integration initialization."""

from unittest.mock import MagicMock

from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import pytest
import requests
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.proxmoxve.const import (
    AUTH_PAM,
    CONF_AUTH_METHOD,
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_VMS,
    DOMAIN,
)
from homeassistant.components.proxmoxve.coordinator import (
    ProxmoxNodesNotFoundError,
    ProxmoxPermissionsError,
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

from tests.common import MockConfigEntry, async_load_json_array_fixture


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
    ("exception", "expected_state", "target"),
    [
        (
            AuthenticationError("Invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
            "access.permissions.get",
        ),
        (
            SSLError("SSL handshake failed"),
            ConfigEntryState.SETUP_ERROR,
            "access.permissions.get",
        ),
        (
            ConnectTimeout("Connection timed out"),
            ConfigEntryState.SETUP_RETRY,
            "access.permissions.get",
        ),
        (
            ResourceException(403, "Forbidden", ""),
            ConfigEntryState.SETUP_ERROR,
            "access.permissions.get",
        ),
        (
            ResourceException(500, "Internal Server Error", ""),
            ConfigEntryState.SETUP_RETRY,
            "access.permissions.get",
        ),
        (
            ResourceException(403, "Forbidden", ""),
            ConfigEntryState.SETUP_ERROR,
            "nodes.get",
        ),
        (
            ResourceException(500, "Internal Server Error", ""),
            ConfigEntryState.SETUP_RETRY,
            "nodes.get",
        ),
        (
            requests.exceptions.ConnectionError("Connection refused"),
            ConfigEntryState.SETUP_ERROR,
            "access.permissions.get",
        ),
        (
            ProxmoxPermissionsError("Failed to retrieve permissions"),
            ConfigEntryState.SETUP_ERROR,
            "access.permissions.get",
        ),
        (
            ProxmoxNodesNotFoundError("No nodes found"),
            ConfigEntryState.SETUP_ERROR,
            "nodes.get",
        ),
    ],
    ids=[
        "auth_error",
        "ssl_error",
        "connect_timeout",
        "resource_exception_permissions_403",
        "resource_exception_permissions_500",
        "resource_exception_nodes_403",
        "resource_exception_nodes_500",
        "connection_error",
        "permissions_error",
        "nodes_not_found",
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
    target: str,
) -> None:
    """Test the _async_setup."""
    attr_to_mock = mock_proxmox_client
    for part in target.split("."):
        attr_to_mock = getattr(attr_to_mock, part)
    attr_to_mock.side_effect = exception

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == expected_state


async def test_migration_v1_to_v3(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test migration from version 1."""
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

    assert entry.version == 3

    vm_entity_after = entity_registry.async_get(vm_entity.entity_id)
    container_entity_after = entity_registry.async_get(container_entity.entity_id)

    assert vm_entity_after.unique_id == f"{entry.entry_id}_100_status"
    assert container_entity_after.unique_id == f"{entry.entry_id}_200_status"


async def test_migration_v2_to_v3(
    hass: HomeAssistant,
) -> None:
    """Test migration from version 2 to 3."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
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
    assert entry.version == 2

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    assert entry.data[CONF_AUTH_METHOD] == AUTH_PAM
    assert entry.data[CONF_REALM] == AUTH_PAM


async def test_new_vm_creates_entity(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a VM appearing after initial load gets an entity created."""
    mock_proxmox_client._node_mock.qemu.get.return_value = []
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == ConfigEntryState.LOADED

    initial_count = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )

    mock_proxmox_client._node_mock.qemu.get.return_value = (
        await async_load_json_array_fixture(hass, "nodes/qemu.json", DOMAIN)
    )

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        > initial_count
    )


async def test_new_container_creates_entity(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a container appearing after initial load gets an entity created."""
    mock_proxmox_client._node_mock.lxc.get.return_value = []
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state == ConfigEntryState.LOADED

    initial_count = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )

    mock_proxmox_client._node_mock.lxc.get.return_value = (
        await async_load_json_array_fixture(hass, "nodes/lxc.json", DOMAIN)
    )

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        > initial_count
    )
