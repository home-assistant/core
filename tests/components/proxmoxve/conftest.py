"""Common fixtures for the ProxmoxVE tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from aioproxmox import ProxmoxVE
from aioproxmox.endpoints import (
    AccessEndpoint,
    ClusterEndpoint,
    LXCActionProperty,
    LXCEndpoint,
    LXCStatusEndpoint,
    NodeActionProperty,
    NodeAptEndpoint,
    NodeEndpoint,
    NodeStatusCommand,
    QemuActionProperty,
    QemuEndpoint,
    QemuStatusEndpoint,
)
from aioproxmox.model import PVEPermissions
from aioproxmox.model.pve import (
    ClusterResourcesCollection,
    ContainerResource,
    NodeAptUpdate,
    NodeAptUpdateProperty,
    NodeStorageResource,
    NodeStorageResources,
    NodeTask,
    NodeTasks,
    NodeVersion,
    QemuResource,
)
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

from homeassistant.components.proxmoxve.const import (
    CONF_AUTH_METHOD,
    CONF_CONTAINERS,
    CONF_NODE,
    CONF_NODES,
    CONF_REALM,
    CONF_TOKEN_ID,
    CONF_TOKEN_SECRET,
    CONF_VMS,
    DOMAIN,
    ProxmoxPermission,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TOKEN,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from . import MERGED_PERMISSIONS

# Actions declared as descriptors, which autospec cannot see
_ACTION_DESCRIPTORS = (
    LXCActionProperty,
    NodeActionProperty,
    NodeStatusCommand,
    QemuActionProperty,
)

MOCK_TEST_CONFIG_BASE = {
    CONF_AUTH_METHOD: "pam",
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 8006,
    CONF_REALM: "pam",
    CONF_USERNAME: "test_user@pam",
    CONF_VERIFY_SSL: True,
    CONF_TOKEN: False,
    CONF_NODES: [
        {
            CONF_NODE: "pve1",
            CONF_VMS: [100, 101],
            CONF_CONTAINERS: [200, 201],
        },
    ],
}
MOCK_TEST_CONFIG = {
    **MOCK_TEST_CONFIG_BASE,
    CONF_PASSWORD: "test_password",
}

MOCK_TEST_TOKEN_CONFIG = {
    **MOCK_TEST_CONFIG_BASE,
    CONF_TOKEN: True,
    CONF_TOKEN_ID: "test_token_id",
    CONF_TOKEN_SECRET: "test_token_secret",
}

MOCK_TEST_OTHER_CONFIG = {
    **MOCK_TEST_CONFIG,
    CONF_AUTH_METHOD: "other",
    CONF_REALM: "Test_Realm",
    CONF_USERNAME: "test_user@Test_Realm",
}

MOCK_TEST_TOKEN_OTHER_CONFIG = {
    **MOCK_TEST_CONFIG_BASE,
    CONF_TOKEN: True,
    CONF_TOKEN_ID: "test_token_id",
    CONF_TOKEN_SECRET: "test_token_secret",
    CONF_AUTH_METHOD: "other",
    CONF_REALM: "Test_Realm",
    CONF_USERNAME: "test_user@Test_Realm",
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.proxmoxve.async_setup_entry",
        return_value=None,
    ) as mock_setup:
        yield mock_setup


def _mock_endpoint(endpoint_cls: type) -> MagicMock:
    """Autospec an aioproxmox endpoint, including its descriptor actions."""
    endpoint = create_autospec(endpoint_cls, instance=True)
    for name, attr in vars(endpoint_cls).items():
        if isinstance(attr, _ACTION_DESCRIPTORS):
            setattr(endpoint, name, AsyncMock())
    return endpoint


def _mock_guest(endpoint_cls: type, status_cls: type) -> MagicMock:
    """Mock a QEMU or LXC endpoint, whose status endpoint is set in __init__."""
    guest = create_autospec(endpoint_cls, instance=True)
    guest.status = _mock_endpoint(status_cls)
    return guest


@pytest.fixture
def mock_proxmox_client() -> Generator[MagicMock]:
    """Mock the aioproxmox client, returning typed models built from fixtures."""
    client = create_autospec(ProxmoxVE, instance=True)

    all_cluster_resources = ClusterResourcesCollection.from_dict(
        {"resources": load_json_array_fixture("nodes/nodes.json", DOMAIN)}
    )
    # Only pve1 to match MOCK_TEST_CONFIG; tests swap its `resources`
    client.cluster_resources = ClusterResourcesCollection(
        resources=[node for node in all_cluster_resources if node.node == "pve1"]
    )
    client.cluster = _mock_endpoint(ClusterEndpoint)
    # Like the library, both refresh paths hand back the same collection
    client.connect.return_value = client.cluster_resources
    client.cluster.resources.return_value = client.cluster_resources

    client.access = _mock_endpoint(AccessEndpoint)
    client.access.permissions.return_value = PVEPermissions.from_api_response(
        MERGED_PERMISSIONS
    )

    node = _mock_endpoint(NodeEndpoint)
    qemu_list = [
        QemuResource.from_dict(vm)
        for vm in load_json_array_fixture("nodes/qemu.json", DOMAIN)
    ]
    lxc_list = [
        ContainerResource.from_dict(ct)
        for ct in load_json_array_fixture("nodes/lxc.json", DOMAIN)
    ]
    node.qemu_all.return_value = qemu_list
    node.lxc_all.return_value = lxc_list
    node.storage.return_value = NodeStorageResources(
        storages=NodeStorageResource.list_from_api(
            load_json_array_fixture("nodes/storage.json", DOMAIN)
        )
    )
    node.version.return_value = NodeVersion.from_dict(
        load_json_object_fixture("nodes/version.json", DOMAIN)
    )

    apt = _mock_endpoint(NodeAptEndpoint)
    apt.update.return_value = NodeAptUpdate(
        items=[
            NodeAptUpdateProperty.from_dict(item)
            for item in load_json_array_fixture("nodes/update.json", DOMAIN)
        ]
    )
    node.apt.return_value = apt

    tasks = NodeTask.list_from_api(load_json_array_fixture("nodes/tasks.json", DOMAIN))

    def _tasks(**kwargs: Any) -> NodeTasks:
        """Return backup tasks only when the user may audit nodes."""
        permissions: PVEPermissions = client.access.permissions.return_value
        if not permissions.has_permission("/nodes", ProxmoxPermission.SYSAUDIT):
            return NodeTasks(tasks=[])
        return NodeTasks(tasks=tasks)

    node.tasks.side_effect = _tasks

    # Kept per vmid so tests can assert on the action of a specific guest
    qemu_mocks = {
        vm.vmid: _mock_guest(QemuEndpoint, QemuStatusEndpoint) for vm in qemu_list
    }
    lxc_mocks = {
        ct.vmid: _mock_guest(LXCEndpoint, LXCStatusEndpoint) for ct in lxc_list
    }
    node.qemu.side_effect = qemu_mocks.__getitem__
    node.lxc.side_effect = lxc_mocks.__getitem__

    client.nodes.return_value = node

    client._node_mock = node
    client._qemu_mocks = qemu_mocks
    client._lxc_mocks = lxc_mocks
    client._all_cluster_resources = all_cluster_resources

    with (
        patch(
            "homeassistant.components.proxmoxve.coordinator.ProxmoxVE",
            autospec=True,
            return_value=client,
        ),
        patch(
            "homeassistant.components.proxmoxve.config_flow.ProxmoxVE",
            autospec=True,
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ProxmoxVE test",
        data=MOCK_TEST_CONFIG,
        entry_id="1234",
    )


@pytest.fixture
def mock_config_entry_token_other() -> MockConfigEntry:
    """Mock a config entry with token authentication on different realm."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ProxmoxVE test",
        data=MOCK_TEST_TOKEN_OTHER_CONFIG,
        entry_id="1234",
    )
