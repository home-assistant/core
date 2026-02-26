"""Common fixtures for the portainer tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyportainer.models.docker import (
    DockerContainer,
    DockerContainerStats,
    DockerSystemDF,
    LocalImageInformation,
    PortainerImageUpdateStatus,
)
from pyportainer.models.docker_inspect import DockerInfo, DockerInspect, DockerVersion
from pyportainer.models.portainer import Endpoint
from pyportainer.watcher import PortainerImageWatcherResult
from pyportainer.models.stacks import Stack
import pytest

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_value_fixture,
)

MOCK_TEST_CONFIG = {
    CONF_URL: "https://127.0.0.1:9000/",
    CONF_API_TOKEN: "test_api_token",
    CONF_VERIFY_SSL: True,
}

TEST_ENTRY = "portainer_test_entry_123"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.portainer.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_portainer_watcher() -> Generator[MagicMock]:
    """Mock PortainerImageWatcher with no results by default."""
    with patch(
        "homeassistant.components.portainer.PortainerImageWatcher", autospec=True
    ) as mock_watcher_class:
        watcher = mock_watcher_class.return_value
        watcher.results = {
            (
                1,
                "aa86eacfb3b3ed4cd362c1e88fc89a53908ad05fb3a4103bca3f9b28292d14bf",
            ): PortainerImageWatcherResult(
                endpoint_id=1,
                container_id="aa86eacfb3b3ed4cd362c1e88fc89a53908ad05fb3a4103bca3f9b28292d14bf",
                status=PortainerImageUpdateStatus(
                    update_available=True,
                    local_digest="sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96",
                    registry_digest="sha256:newdigest123456789",
                ),
            )
        }
        yield watcher


@pytest.fixture
def mock_portainer_client(mock_portainer_watcher: MagicMock) -> Generator[AsyncMock]:
    """Mock Portainer client with dynamic exception injection support."""
    with (
        patch(
            "homeassistant.components.portainer.Portainer", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.portainer.config_flow.Portainer", new=mock_client
        ),
    ):
        client = mock_client.return_value

        client.get_endpoints.return_value = [
            Endpoint.from_dict(endpoint)
            for endpoint in load_json_array_fixture("endpoints.json", DOMAIN)
        ]
        client.get_containers.return_value = [
            DockerContainer.from_dict(container)
            for container in load_json_array_fixture("containers.json", DOMAIN)
        ]
        client.docker_info.return_value = DockerInfo.from_dict(
            load_json_value_fixture("docker_info.json", DOMAIN)
        )
        client.docker_version.return_value = DockerVersion.from_dict(
            load_json_value_fixture("docker_version.json", DOMAIN)
        )
        client.container_stats.return_value = DockerContainerStats.from_dict(
            load_json_value_fixture("container_stats.json", DOMAIN)
        )
        client.docker_system_df.return_value = DockerSystemDF.from_dict(
            load_json_value_fixture("docker_system_df.json", DOMAIN)
        )
        client.inspect_container.return_value = DockerInspect.from_dict(
            load_json_value_fixture("container_inspect.json", DOMAIN)
        )
        client.get_image.return_value = LocalImageInformation.from_dict(
            load_json_value_fixture("local_image_information.json", DOMAIN)
        )

        client.restart_container = AsyncMock(return_value=None)
        client.images_prune = AsyncMock(return_value=None)
        client.container_recreate = AsyncMock(return_value=None)
        client.get_stacks.return_value = [
            Stack.from_dict(stack)
            for stack in load_json_array_fixture("stacks.json", DOMAIN)
        ]

        client.restart_container = AsyncMock(return_value=None)
        client.images_prune = AsyncMock(return_value=None)
        client.start_container = AsyncMock(return_value=None)
        client.stop_container = AsyncMock(return_value=None)
        client.start_stack = AsyncMock(return_value=None)
        client.stop_stack = AsyncMock(return_value=None)

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Portainer test",
        data=MOCK_TEST_CONFIG,
        unique_id=MOCK_TEST_CONFIG[CONF_API_TOKEN],
        entry_id=TEST_ENTRY,
        version=2,
    )
