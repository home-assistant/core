"""Music Assistant test fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

from music_assistant_client.music import Music
from music_assistant_client.player_queues import PlayerQueues
from music_assistant_client.players import Players
from music_assistant_models.api import ServerInfoMessage
import pytest

from homeassistant.components.music_assistant.config_flow import CONF_URL
from homeassistant.components.music_assistant.const import DOMAIN

from tests.common import AsyncMock, MockConfigEntry, load_fixture

MOCK_SERVER_ID = "1234"


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


@pytest.fixture(name="music_assistant_client")
async def music_assistant_client_fixture() -> AsyncGenerator[MagicMock]:
    """Fixture for a Music Assistant client."""
    with patch(
        "homeassistant.components.music_assistant.MusicAssistantClient", autospec=True
    ) as client_class:
        client = client_class.return_value

        async def connect() -> None:
            """Mock connect."""
            await asyncio.sleep(0)

        async def listen(init_ready: asyncio.Event | None) -> None:
            """Mock listen."""
            if init_ready is not None:
                init_ready.set()
            listen_block = asyncio.Event()
            await listen_block.wait()
            pytest.fail("Listen was not cancelled!")

        client.connect = AsyncMock(side_effect=connect)
        client.start_listening = AsyncMock(side_effect=listen)
        client.server_info = ServerInfoMessage(
            server_id=MOCK_SERVER_ID,
            server_version="0.0.0",
            schema_version=1,
            min_supported_schema_version=1,
            base_url="http://localhost:8095",
            homeassistant_addon=False,
            onboard_done=True,
        )
        client.connection = MagicMock()
        client.connection.connected = True
        client.players = Players(client)
        client.player_queues = PlayerQueues(client)
        client.music = Music(client)
        client.server_url = client.server_info.base_url
        client.get_media_item_image_url = MagicMock(return_value=None)

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
