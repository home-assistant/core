"""Common fixtures for the Pterodactyl tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from pydactyl.responses import PaginatedResponse
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.pterodactyl.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL

from .const import SERVER_1_IDENTIFIER, SERVER_2_IDENTIFIER, TEST_API_KEY, TEST_URL


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pterodactyl.async_setup_entry", return_value=None
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
def game_server_data() -> dict[str, dict[str, Any]]:
    """Return mock game server data."""
    return {
        SERVER_1_IDENTIFIER: load_json_object_fixture("server_1_data.json", DOMAIN),
        SERVER_2_IDENTIFIER: load_json_object_fixture("server_2_data.json", DOMAIN),
    }


@pytest.fixture
def suspended_game_servers(game_server_data: dict[str, dict[str, Any]]) -> None:
    """Mark all mock game servers as suspended."""
    for data in game_server_data.values():
        data["is_suspended"] = True


@pytest.fixture
def mock_pterodactyl(
    game_server_data: dict[str, dict[str, Any]],
) -> Generator[AsyncMock]:
    """Mock the Pterodactyl API."""
    with patch(
        "homeassistant.components.pterodactyl.api.AsyncPterodactylClient", autospec=True
    ) as mock:
        server_list_data = load_json_object_fixture("server_list_data.json", DOMAIN)
        utilization_data = load_json_object_fixture("utilization_data.json", DOMAIN)

        mock.return_value.client.servers.list_servers = AsyncMock(
            return_value=PaginatedResponse(
                mock.return_value, "client", server_list_data
            )
        )
        mock.return_value.client.servers.get_server = AsyncMock(
            side_effect=lambda identifier: game_server_data[identifier]
        )
        mock.return_value.client.servers.get_server_utilization = AsyncMock(
            return_value=utilization_data
        )

        yield mock.return_value
