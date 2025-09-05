"""Common fixtures for the ProxmoxVE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

MOCK_TEST_CONFIG = {
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
        }
    ],
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
            "homeassistant.components.proxmoxve.ProxmoxAPI", autospec=True
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

        # Make a separate mock for the qemu and lxc endpoints
        node_mock = MagicMock()
        node_mock.qemu.get.return_value = load_json_array_fixture(
            "nodes/qemu.json", DOMAIN
        )
        node_mock.lxc.get.return_value = load_json_array_fixture(
            "nodes/lxc.json", DOMAIN
        )

        nodes_mock = MagicMock()
        nodes_mock.get.return_value = load_json_array_fixture(
            "nodes/nodes.json", DOMAIN
        )
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
    )
