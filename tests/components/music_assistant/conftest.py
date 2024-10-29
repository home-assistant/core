"""Music Assistant test fixtures."""

from collections.abc import Generator
from unittest.mock import patch

from music_assistant.common.models.api import ServerInfoMessage
import pytest

from homeassistant.components.music_assistant.config_flow import CONF_URL
from homeassistant.components.music_assistant.const import DOMAIN

from tests.common import MockConfigEntry, load_fixture
from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.music_assistant.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_get_server_info() -> Generator[AsyncMock]:
    """Mock the function to get server info."""
    with patch(
        "homeassistant.components.music_assistant.config_flow.get_server_info"
    ) as mock_get_server_info:
        mock_get_server_info.return_value = ServerInfoMessage.from_json(
            load_fixture("server_info_message.json", DOMAIN)
        )
        yield mock_get_server_info


@pytest.fixture
def mock_music_assistant_client() -> Generator[AsyncMock]:
    """Mock an Music Assistant client."""
    with (
        patch(
            "homeassistant.components.music_assistant.MusicAssistantClient",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        client.host = "127.0.0.1"

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Music Assistant",
        data={CONF_URL: "http://localhost:8095"},
        unique_id="1234",
    )
