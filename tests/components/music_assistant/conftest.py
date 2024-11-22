"""Music Assistant test fixtures."""

from collections.abc import Generator
from unittest.mock import patch

from music_assistant_models.api import ServerInfoMessage
import pytest

from homeassistant.components.music_assistant.config_flow import CONF_URL
from homeassistant.components.music_assistant.const import DOMAIN

from tests.common import AsyncMock, MockConfigEntry, load_fixture


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
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Music Assistant",
        data={CONF_URL: "http://localhost:8095"},
        unique_id="1234",
    )
