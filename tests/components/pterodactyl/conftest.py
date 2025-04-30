"""Common fixtures for the Pterodactyl tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pydactyl.responses import PaginatedResponse
import pytest

from homeassistant.components.pterodactyl.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL

from .const import TEST_API_KEY, TEST_URL

from tests.common import MockConfigEntry, load_json_object_fixture


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
def mock_pterodactyl() -> Generator[AsyncMock]:
    """Mock the Pterodactyl API."""
    with patch(
        "homeassistant.components.pterodactyl.api.PterodactylClient", autospec=True
    ) as mock:
        server_list_data = load_json_object_fixture("server_list_data.json", DOMAIN)
        server_1_data = load_json_object_fixture("server_1_data.json", DOMAIN)
        server_2_data = load_json_object_fixture("server_2_data.json", DOMAIN)
        utilization_data = load_json_object_fixture("utilization_data.json", DOMAIN)

        mock.return_value.client.servers.list_servers.return_value = PaginatedResponse(
            mock.return_value, "client", server_list_data
        )
        mock.return_value.client.servers.get_server.side_effect = [
            server_1_data,
            server_2_data,
        ]
        mock.return_value.client.servers.get_server_utilization.return_value = (
            utilization_data
        )

        yield mock.return_value
