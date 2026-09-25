"""Tests for the Proxmox VE integration initialization."""

from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import pytest
import requests
from requests.exceptions import ConnectTimeout, SSLError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.proxmoxve.const import (
    AUTH_OTHER,
    AUTH_PAM,
    CONF_AUTH_METHOD,
    CONF_REALM,
    DOMAIN,
)
from homeassistant.components.proxmoxve.coordinator import (
    DEFAULT_UPDATE_INTERVAL,
    ProxmoxNodesNotFoundError,
    ProxmoxPermissionsError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
)


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
    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("mock_config_entry", "expected_auth_method", "expected_realm"),
    [
        (
            MockConfigEntry(
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
            ),
            AUTH_PAM,
            "pam",
        ),
        (
            MockConfigEntry(
                domain=DOMAIN,
                version=1,
                unique_id="1",
                data={
                    CONF_HOST: "http://test_host",
                    CONF_PORT: 8006,
                    CONF_REALM: "Test_Realm",
                    CONF_USERNAME: "test_user@Test_Realm",
                    CONF_PASSWORD: "test_password",
                    CONF_VERIFY_SSL: True,
                },
            ),
            AUTH_OTHER,
            "Test_Realm",
        ),
    ],
)
async def test_migration_v1_to_v3(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    expected_auth_method: str,
    expected_realm: str,
) -> None:
    """Test migration from version 1 to 3."""
    entry = mock_config_entry

    entry.add_to_hass(hass)
    assert entry.version == 1

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
    assert entry.data[CONF_AUTH_METHOD] == expected_auth_method
    assert entry.data[CONF_REALM] == expected_realm

    vm_entity_after = entity_registry.async_get(vm_entity.entity_id)
    container_entity_after = entity_registry.async_get(container_entity.entity_id)

    assert vm_entity_after.unique_id == f"{entry.entry_id}_100_status"
    assert container_entity_after.unique_id == f"{entry.entry_id}_200_status"


@pytest.mark.parametrize(
    ("mock_config_entry", "expected_auth_method", "expected_realm"),
    [
        (
            MockConfigEntry(
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
            ),
            AUTH_PAM,
            "pam",
        ),
        (
            MockConfigEntry(
                domain=DOMAIN,
                version=2,
                unique_id="1",
                data={
                    CONF_HOST: "http://test_host",
                    CONF_PORT: 8006,
                    CONF_REALM: "Test_Realm",
                    CONF_USERNAME: "test_user@Test_Realm",
                    CONF_PASSWORD: "test_password",
                    CONF_VERIFY_SSL: True,
                },
            ),
            AUTH_OTHER,
            "Test_Realm",
        ),
        (
            MockConfigEntry(
                domain=DOMAIN,
                version=2,
                unique_id="1",
                data={
                    CONF_HOST: "http://test_host",
                    CONF_PORT: 8006,
                    CONF_USERNAME: "test_user@pam",
                    CONF_PASSWORD: "test_password",
                    CONF_VERIFY_SSL: True,
                },
            ),
            AUTH_PAM,
            "pam",
        ),
        (
            MockConfigEntry(
                domain=DOMAIN,
                version=2,
                unique_id="1",
                data={
                    CONF_HOST: "http://test_host",
                    CONF_PORT: 8006,
                    CONF_USERNAME: "test_user@Test_Realm",
                    CONF_PASSWORD: "test_password",
                    CONF_VERIFY_SSL: True,
                },
            ),
            AUTH_OTHER,
            "Test_Realm",
        ),
    ],
)
async def test_migration_v2_to_v3(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_auth_method: str,
    expected_realm: str,
) -> None:
    """Test migration from version 2 to 3."""
    entry = mock_config_entry

    entry.add_to_hass(hass)
    assert entry.version == 2

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    assert entry.data[CONF_AUTH_METHOD] == expected_auth_method
    assert entry.data[CONF_REALM] == expected_realm


async def test_offline_node(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an offline node doesn't cause the entire update to fail."""
    mock_proxmox_client.nodes.get.return_value = mock_proxmox_client._all_nodes
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("binary_sensor.pve1_status")
    assert state.state == STATE_ON

    state = hass.states.get("binary_sensor.pve3_status")
    assert state.state == STATE_OFF


async def test_new_vm_creates_entity(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a VM appearing after initial load gets an entity created."""
    mock_proxmox_client._node_mock.qemu.get.return_value = []
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

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
    assert mock_config_entry.state is ConfigEntryState.LOADED

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


@pytest.mark.parametrize(
    "child_identifier",
    ["vm_100", "vm_101", "container_200", "container_201", "storage_local"],
)
@pytest.mark.usefixtures("mock_proxmox_client")
async def test_child_devices_link_to_node(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    child_identifier: str,
) -> None:
    """Test that VM/container/storage devices link to their node via via_device_id."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    entry_id = mock_config_entry.entry_id
    node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_node_node/pve1"), entry_id
    )
    assert node_device is not None

    child_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_{child_identifier}"), entry_id
    )
    assert child_device is not None
    assert child_device.via_device_id == node_device.id


async def test_new_node_registers_device_before_children(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a node discovered after setup registers its device before its children.

    Regression test for a race where a newly discovered node's VM/container/
    storage entities were built before the node's own device was registered,
    causing via_device_id resolution to raise ValueError.

    Without audit permissions the node surfaces no entities of its own, so the
    node device is only registered by the coordinator: without that explicit
    registration its child (the configured VM, whose entities are always
    created) cannot resolve its via_device_id.
    """
    mock_proxmox_client.access.permissions.get.return_value = {}

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # setup_integration enables disabled-by-default entities, which schedules a
    # debounced config entry reload; let it settle so it doesn't coincide with
    # (and mask, via a fresh setup) the refresh that discovers the new node.
    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # A second node, bringing its own VM, appears on the next refresh.
    pve2_vm = {
        **(await async_load_json_array_fixture(hass, "nodes/qemu.json", DOMAIN))[0],
        "vmid": 300,
        "name": "vm-pve2",
    }
    pve2_node_mock = MagicMock()
    pve2_node_mock.qemu.get.return_value = [pve2_vm]
    pve2_node_mock.lxc.get.return_value = []
    pve2_node_mock.storage.get.return_value = []
    pve2_node_mock.tasks.get.return_value = []

    default_node_mock = mock_proxmox_client._node_mock
    mock_proxmox_client._nodes_mock.side_effect = lambda node: (
        pve2_node_mock if node == "pve2" else default_node_mock
    )
    mock_proxmox_client.nodes.get.return_value = [
        node
        for node in mock_proxmox_client._all_nodes
        if node["node"] in ("pve1", "pve2")
    ]

    freezer.tick(DEFAULT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entry_id = mock_config_entry.entry_id
    node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_node_node/pve2"), entry_id
    )
    assert node_device is not None

    vm_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_vm_300"), entry_id
    )
    assert vm_device is not None
    assert vm_device.via_device_id == node_device.id

    # The new node's VM entity was built and populated from the refresh.
    state = hass.states.get("binary_sensor.vm_pve2_status")
    assert state is not None
    assert state.state == STATE_ON


async def test_stale_devices_removed(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that devices are removed when their resource disappears."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    entry_id = mock_config_entry.entry_id
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_vm_100"), entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_vm_101"), entry_id
    )

    # VM 100 is gone, VM 101 remains
    mock_proxmox_client._node_mock.qemu.get.return_value = [
        vm
        for vm in await async_load_json_array_fixture(hass, "nodes/qemu.json", DOMAIN)
        if vm["vmid"] != 100
    ]

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{entry_id}_vm_100"), entry_id
        )
        is None
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_vm_101"), entry_id
    )


def _full_node(node_name: str) -> dict[str, Any]:
    """Return a complete Proxmox node response."""
    return {
        "id": f"node/{node_name}",
        "node": node_name,
        "status": "online",
        "level": "",
        "type": "node",
        "maxmem": 34359738368,
        "mem": 12884901888,
        "maxcpu": 8,
        "cpu": 0.12,
        "uptime": 86400,
        "maxdisk": 500000000000,
        "disk": 100000000000,
        "ssl_fingerprint": "AA:BB:CC:...:DD",
    }


_VM_100 = {
    "vmid": 100,
    "name": "vm-web",
    "status": "running",
    "maxmem": 2147483648,
    "cpus": 2,
    "mem": 1073741824,
    "cpu": 0.15,
    "maxdisk": 34359738368,
    "disk": 1234567890,
    "uptime": 86400,
}

_VM_101 = {
    "vmid": 101,
    "name": "vm-db",
    "status": "stopped",
    "maxmem": 2147483648,
    "cpus": 2,
    "mem": 1073741824,
    "cpu": 0.15,
    "maxdisk": 34359738368,
    "disk": 1234567890,
    "uptime": 86400,
}

_CT_200 = {
    "vmid": "200",
    "name": "ct-nginx",
    "status": "running",
    "maxmem": 1073741824,
    "cpus": 1,
    "mem": 536870912,
    "cpu": 0.05,
    "maxdisk": 21474836480,
    "disk": 1125899906,
    "uptime": 43200,
}

_CT_201 = {
    "vmid": "201",
    "name": "ct-backup",
    "status": "stopped",
    "maxmem": 1073741824,
    "cpus": 1,
    "mem": 536870912,
    "cpu": 0.05,
    "maxdisk": 21474836480,
    "disk": 1125899906,
    "uptime": 43200,
}


def _set_cluster_data(
    mock_proxmox_client: MagicMock,
    resources: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]],
    node_order: tuple[str, ...] | None = None,
) -> dict[str, MagicMock]:
    """Configure the mocked API responses for each node."""
    node_mocks: dict[str, MagicMock] = {}
    for node_name, (vms, containers) in resources.items():
        node_mock = MagicMock()
        node_mock.qemu.get.return_value = vms
        node_mock.lxc.get.return_value = containers
        node_mock.storage.get.return_value = []
        node_mock.tasks.get.return_value = []
        node_mocks[node_name] = node_mock

    mock_proxmox_client._nodes_mock.side_effect = node_mocks.__getitem__
    mock_proxmox_client.nodes.get.return_value = [
        _full_node(node_name) for node_name in node_order or tuple(resources)
    ]
    return node_mocks


def _get_entity_id(
    entity_registry: er.EntityRegistry, entry_id: str, unique_id_suffix: str
) -> str:
    """Look up an entity ID by unique ID suffix."""
    for entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        if entry.unique_id.endswith(unique_id_suffix):
            return entry.entity_id
    raise AssertionError(f"No entity found with unique ID ending in {unique_id_suffix}")


def _state_value(hass: HomeAssistant, entity_id: str) -> str:
    """Return an entity state after proving that it exists."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def _resource_entity_identity(
    entity_registry: er.EntityRegistry, entry_id: str, resource_id: int
) -> dict[str, tuple[str, str]]:
    """Return the public registry identity of every entity for a resource."""
    unique_id_prefix = f"{entry_id}_{resource_id}_"
    return {
        entry.unique_id: (entry.entity_id, entry.id)
        for entry in er.async_entries_for_config_entry(entity_registry, entry_id)
        if entry.unique_id.startswith(unique_id_prefix)
    }


def _get_child_device(
    device_registry: dr.DeviceRegistry,
    entry_id: str,
    resource_kind: str,
    resource_id: int,
) -> dr.DeviceEntry:
    """Return a VM/container device from the registry."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_{resource_kind}_{resource_id}"), entry_id
    )
    assert device is not None
    return device


def _matching_device_count(
    device_registry: dr.DeviceRegistry,
    entry_id: str,
    resource_kind: str,
    resource_id: int,
) -> int:
    """Count registry devices matching one Proxmox resource identifier."""
    identifier = (DOMAIN, f"{entry_id}_{resource_kind}_{resource_id}")
    return sum(
        identifier in device.identifiers
        for device in dr.async_entries_for_config_entry(device_registry, entry_id)
    )


@pytest.mark.parametrize(
    ("resource_kind", "resource_id", "endpoint"),
    [("vm", 100, "qemu"), ("container", 200, "lxc")],
)
async def test_migration_source_dual_target(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    resource_kind: str,
    resource_id: int,
    endpoint: str,
) -> None:
    """Test migration uses public polling and keeps registry identity stable."""
    initial_vms = [_VM_100, _VM_101]
    initial_containers = [_CT_200, _CT_201]
    _set_cluster_data(
        mock_proxmox_client,
        {"pve1": (initial_vms, initial_containers)},
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR, Platform.BUTTON],
    ):
        await setup_integration(hass, mock_config_entry)

    entry_id = mock_config_entry.entry_id
    status_entity_id = _get_entity_id(
        entity_registry, entry_id, f"{resource_id}_status"
    )
    button_entity_id = _get_entity_id(
        entity_registry, entry_id, f"{resource_id}_restart"
    )
    assert _state_value(hass, status_entity_id) == STATE_ON

    initial_entity_identity = _resource_entity_identity(
        entity_registry, entry_id, resource_id
    )
    assert initial_entity_identity
    source_node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_node_node/pve1"), entry_id
    )
    assert source_node_device is not None
    child_device = _get_child_device(
        device_registry, entry_id, resource_kind, resource_id
    )
    child_device_id = child_device.id
    assert child_device.via_device_id == source_node_device.id

    target_resource = {
        **(_VM_100 if resource_kind == "vm" else _CT_200),
        "status": "stopped",
    }
    target_vms = [target_resource] if resource_kind == "vm" else []
    target_containers = [target_resource] if resource_kind == "container" else []
    _set_cluster_data(
        mock_proxmox_client,
        {
            "pve1": (initial_vms, initial_containers),
            "pve2": (target_vms, target_containers),
        },
    )
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    target_node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_node_node/pve2"), entry_id
    )
    assert target_node_device is not None
    assert _state_value(hass, status_entity_id) == STATE_ON
    assert (
        _resource_entity_identity(entity_registry, entry_id, resource_id)
        == initial_entity_identity
    )
    assert (
        _get_child_device(device_registry, entry_id, resource_kind, resource_id).id
        == child_device_id
    )
    assert (
        _get_child_device(
            device_registry, entry_id, resource_kind, resource_id
        ).via_device_id
        == source_node_device.id
    )

    source_vms = [_VM_101] if resource_kind == "vm" else initial_vms
    source_containers = (
        [_CT_201] if resource_kind == "container" else initial_containers
    )
    target_node_mocks = _set_cluster_data(
        mock_proxmox_client,
        {
            "pve1": (source_vms, source_containers),
            "pve2": (target_vms, target_containers),
        },
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state_value(hass, status_entity_id) == STATE_OFF
    assert (
        _resource_entity_identity(entity_registry, entry_id, resource_id)
        == initial_entity_identity
    )
    assert (
        _get_child_device(device_registry, entry_id, resource_kind, resource_id).id
        == child_device_id
    )
    assert (
        _get_child_device(
            device_registry, entry_id, resource_kind, resource_id
        ).via_device_id
        == target_node_device.id
    )
    assert (
        _matching_device_count(device_registry, entry_id, resource_kind, resource_id)
        == 1
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: button_entity_id},
        blocking=True,
    )

    target_endpoint = getattr(target_node_mocks["pve2"], endpoint)
    target_endpoint.assert_called_once_with(resource_id)
    target_endpoint.return_value.status.reboot.post.assert_called_once_with()


@pytest.mark.parametrize("node_order", [("pve1", "pve2"), ("pve2", "pve1")])
async def test_new_dual_node_resources_choose_node_deterministically(
    hass: HomeAssistant,
    mock_proxmox_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    node_order: tuple[str, str],
) -> None:
    """Test new dual-node resources choose the same observable parent device."""
    _set_cluster_data(
        mock_proxmox_client,
        {"pve1": ([_VM_100, _VM_101], [_CT_200, _CT_201])},
    )

    with patch(
        "homeassistant.components.proxmoxve.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    new_vm_source = {**_VM_100, "vmid": 999, "name": "vm-new"}
    new_vm_target = {**new_vm_source, "status": "stopped"}
    new_container_source = {**_CT_200, "vmid": 888, "name": "ct-new"}
    new_container_target = {**new_container_source, "status": "stopped"}
    _set_cluster_data(
        mock_proxmox_client,
        {
            "pve1": (
                [_VM_100, _VM_101, new_vm_source],
                [_CT_200, _CT_201, new_container_source],
            ),
            "pve2": ([new_vm_target], [new_container_target]),
        },
        node_order,
    )

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entry_id = mock_config_entry.entry_id
    source_node_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{entry_id}_node_node/pve1"), entry_id
    )
    assert source_node_device is not None

    for resource_kind, resource_id in (("vm", 999), ("container", 888)):
        status_entity_id = _get_entity_id(
            entity_registry, entry_id, f"{resource_id}_status"
        )
        assert _state_value(hass, status_entity_id) == STATE_ON
        child_device = _get_child_device(
            device_registry, entry_id, resource_kind, resource_id
        )
        assert child_device.via_device_id == source_node_device.id
        assert (
            _matching_device_count(
                device_registry, entry_id, resource_kind, resource_id
            )
            == 1
        )
