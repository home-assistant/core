"""Common fixtures for the ProxmoxVE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
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
    CONF_REALM: "test_realm",
    CONF_USERNAME: "test_user@test_realm",
}

MOCK_TEST_TOKEN_OTHER_CONFIG = {
    **MOCK_TEST_CONFIG_BASE,
    CONF_TOKEN: True,
    CONF_TOKEN_ID: "test_token_id",
    CONF_TOKEN_SECRET: "test_token_secret",
    CONF_AUTH_METHOD: "other",
    CONF_REALM: "test_realm",
    CONF_USERNAME: "test_user@test_realm",
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.proxmoxve.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_proxmox_client():
    """Mock Proxmox client with dynamic exception injection support."""
    with (
        patch(
            "homeassistant.components.proxmoxve.coordinator.ProxmoxAPI", autospec=True
        ) as mock_api,
        patch(
            "homeassistant.components.proxmoxve.config_flow.ProxmoxAPI"
        ) as mock_api_cf,
    ):
        mock_instance = MagicMock()
        mock_api.return_value = mock_instance
        mock_api_cf.return_value = mock_instance

        mock_instance.access.ticket.post.return_value = load_json_object_fixture(
            "access_ticket.json", DOMAIN
        )

        # Default privileges as defined
        mock_instance.access.permissions.get.return_value = MERGED_PERMISSIONS

        # Make a separate mock for the qemu and lxc endpoints
        node_mock = MagicMock()
        qemu_list = load_json_array_fixture("nodes/qemu.json", DOMAIN)
        lxc_list = load_json_array_fixture("nodes/lxc.json", DOMAIN)

        node_mock.qemu.get.return_value = qemu_list
        node_mock.lxc.get.return_value = lxc_list

        qemu_by_vmid = {vm["vmid"]: vm for vm in qemu_list}
        lxc_by_vmid = {vm["vmid"]: vm for vm in lxc_list}

        # Cache resource mocks by vmid so callers (e.g. button tests) can
        # inspect specific call counts after pressing a button.
        qemu_mocks: dict[int, MagicMock] = {}
        lxc_mocks: dict[int, MagicMock] = {}

        def _qemu_resource(vmid: int) -> MagicMock:
            """Return a cached mock resource for a QEMU VM."""
            if vmid not in qemu_mocks:
                resource = MagicMock()
                vm = qemu_by_vmid[vmid]
                resource.status.current.get.return_value = {
                    "name": vm["name"],
                    "status": vm["status"],
                }
                qemu_mocks[vmid] = resource
            return qemu_mocks[vmid]

        def _lxc_resource(vmid: int) -> MagicMock:
            """Return a cached mock resource for an LXC container."""
            if vmid not in lxc_mocks:
                resource = MagicMock()
                ct = lxc_by_vmid[vmid]
                resource.status.current.get.return_value = {
                    "name": ct["name"],
                    "status": ct["status"],
                }
                lxc_mocks[vmid] = resource
            return lxc_mocks[vmid]

        node_mock.qemu.side_effect = _qemu_resource
        node_mock.lxc.side_effect = _lxc_resource

        mock_instance._qemu_mocks = qemu_mocks
        mock_instance._lxc_mocks = lxc_mocks

        nodes_mock = MagicMock()
        all_nodes = load_json_array_fixture("nodes/nodes.json", DOMAIN)
        # Filter to only pve1 to match MOCK_TEST_CONFIG
        nodes_mock.get.return_value = [n for n in all_nodes if n["node"] == "pve1"]
        nodes_mock.__getitem__.side_effect = lambda key: node_mock
        nodes_mock.return_value = node_mock

        mock_instance.nodes = nodes_mock
        mock_instance._node_mock = node_mock
        mock_instance._nodes_mock = nodes_mock

        yield mock_instance


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
