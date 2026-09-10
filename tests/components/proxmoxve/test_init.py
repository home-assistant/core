"""Tests for the Proxmox VE integration initialization."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from proxmoxer import AuthenticationError
from proxmoxer.core import ResourceException
import pytest
import requests
from requests.exceptions import ConnectTimeout, SSLError

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
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_OFF,
    STATE_ON,
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
