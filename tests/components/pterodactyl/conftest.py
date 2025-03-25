"""Common fixtures for the Pterodactyl tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pydactyl.responses import PaginatedResponse
import pytest

from homeassistant.components.pterodactyl.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL

from tests.common import MockConfigEntry

TEST_URL = "https://192.168.0.1:8080/"
TEST_API_KEY = "TestClientApiKey"
TEST_USER_INPUT = {
    CONF_URL: TEST_URL,
    CONF_API_KEY: TEST_API_KEY,
}
TEST_SERVER_LIST_DATA = {
    "meta": {"pagination": {"total": 2, "count": 2, "per_page": 50, "current_page": 1}},
    "data": [
        {
            "object": "server",
            "attributes": {
                "server_owner": True,
                "identifier": "1",
                "internal_id": 1,
                "uuid": "1-1-1-1-1",
                "name": "Test Server 1",
                "node": "default_node",
                "description": "Description of Test Server 1",
                "limits": {
                    "memory": 2048,
                    "swap": 1024,
                    "disk": 10240,
                    "io": 500,
                    "cpu": 100,
                    "threads": None,
                    "oom_disabled": True,
                },
                "invocation": "java -jar test_server1.jar",
                "docker_image": "test_docker_image_1",
                "egg_features": ["java_version"],
            },
        },
        {
            "object": "server",
            "attributes": {
                "server_owner": True,
                "identifier": "2",
                "internal_id": 2,
                "uuid": "2-2-2-2-2",
                "name": "Test Server 2",
                "node": "default_node",
                "description": "Description of Test Server 2",
                "limits": {
                    "memory": 2048,
                    "swap": 1024,
                    "disk": 10240,
                    "io": 500,
                    "cpu": 100,
                    "threads": None,
                    "oom_disabled": True,
                },
                "invocation": "java -jar test_server_2.jar",
                "docker_image": "test_docker_image2",
                "egg_features": ["java_version"],
            },
        },
    ],
}
TEST_SERVER = {
    "server_owner": True,
    "identifier": "1",
    "internal_id": 1,
    "uuid": "1-1-1-1-1",
    "name": "Test Server 1",
    "node": "default_node",
    "is_node_under_maintenance": False,
    "sftp_details": {"ip": "192.168.0.1", "port": 2022},
    "description": "",
    "limits": {
        "memory": 2048,
        "swap": 1024,
        "disk": 10240,
        "io": 500,
        "cpu": 100,
        "threads": None,
        "oom_disabled": True,
    },
    "invocation": "java -jar test.jar",
    "docker_image": "test_docker_image",
    "egg_features": ["eula", "java_version", "pid_limit"],
    "feature_limits": {"databases": 0, "allocations": 0, "backups": 3},
    "status": None,
    "is_suspended": False,
    "is_installing": False,
    "is_transferring": False,
    "relationships": {"allocations": {...}, "variables": {...}},
}
TEST_SERVER_UTILIZATION = {
    "current_state": "running",
    "is_suspended": False,
    "resources": {
        "memory_bytes": 1111,
        "cpu_absolute": 22,
        "disk_bytes": 3333,
        "network_rx_bytes": 44,
        "network_tx_bytes": 55,
        "uptime": 6666,
    },
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pterodactyl.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create Pterodactyl mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        entry_id="01234567890123456789012345678901",
        title=TEST_URL,
        data={
            CONF_URL: TEST_URL,
            CONF_API_KEY: TEST_API_KEY,
        },
        version=1,
    )


@pytest.fixture
def mock_pterodactyl():
    """Mock the Pterodactyl API."""
    with patch(
        "homeassistant.components.pterodactyl.api.PterodactylClient", autospec=True
    ) as mock:
        mock.return_value.client.servers.list_servers.return_value = PaginatedResponse(
            mock.return_value, "client", TEST_SERVER_LIST_DATA
        )
        mock.return_value.client.servers.get_server.return_value = TEST_SERVER
        mock.return_value.client.servers.get_server_utilization.return_value = (
            TEST_SERVER_UTILIZATION
        )

        yield mock.return_value
