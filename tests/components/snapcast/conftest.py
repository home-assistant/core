"""Test the snapcast config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from snapcast.control.client import Snapclient
from snapcast.control.group import Snapgroup
from snapcast.control.server import CONTROL_PORT
from snapcast.control.stream import Snapstream

from homeassistant.components.snapcast.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.snapcast.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_server(mock_create_server: AsyncMock) -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.snapcast.config_flow.snapcast.control.create_server",
        return_value=mock_create_server,
    ) as mock_server:
        yield mock_server


@pytest.fixture
def mock_create_server(
    mock_group: AsyncMock,
    mock_client: AsyncMock,
    mock_stream_1: AsyncMock,
    mock_stream_2: AsyncMock,
) -> Generator[AsyncMock]:
    """Create mock snapcast connection."""
    with patch(
        "homeassistant.components.snapcast.coordinator.Snapserver", autospec=True
    ) as mock_snapserver:
        mock_server = mock_snapserver.return_value
        mock_server.groups = [mock_group]
        mock_server.clients = [mock_client]
        mock_server.streams = [mock_stream_1, mock_stream_2]
        mock_server.group.return_value = mock_group
        mock_server.client.return_value = mock_client

        def get_stream(identifier: str) -> AsyncMock:
            return {s.identifier: s for s in mock_server.streams}[identifier]

        mock_server.stream = get_stream
        yield mock_server


@pytest.fixture
async def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""

    # Create a mock config entry
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: CONTROL_PORT,
        },
    )


@pytest.fixture
def mock_group(stream: str, streams: dict[str, AsyncMock]) -> AsyncMock:
    """Create a mock Snapgroup."""
    group = AsyncMock(spec=Snapgroup)
    group.identifier = "4dcc4e3b-c699-a04b-7f0c-8260d23c43e1"
    group.name = "test_group"
    group.friendly_name = "test_group"
    group.stream = stream
    group.muted = False
    group.stream_status = streams[stream].status
    group.volume = 48
    group.streams_by_name.return_value = {s.friendly_name: s for s in streams.values()}
    return group


@pytest.fixture
def mock_client(mock_group: AsyncMock) -> AsyncMock:
    """Create a mock Snapclient."""
    client = AsyncMock(spec=Snapclient)
    client.identifier = "00:21:6a:7d:74:fc#2"
    client.friendly_name = "test_client"
    client.version = "0.10.0"
    client.connected = True
    client.name = "Snapclient"
    client.latency = 6
    client.muted = False
    client.volume = 48
    client.group = mock_group
    mock_group.clients = [client.identifier]
    return client


@pytest.fixture
def mock_stream_1() -> AsyncMock:
    """Create a mock stream."""
    stream = AsyncMock(spec=Snapstream)
    stream.identifier = "test_stream_1"
    stream.status = "playing"
    stream.name = "Test Stream 1"
    stream.friendly_name = "Test Stream 1"
    stream.metadata = {
        "album": "Test Album",
        "artist": ["Test Artist 1", "Test Artist 2"],
        "title": "Test Title",
        "artUrl": "http://localhost/test_art.jpg",
        "albumArtist": [
            "Test Album Artist 1",
            "Test Album Artist 2",
        ],
        "trackNumber": 10,
        "duration": 60.0,
    }
    stream.meta = stream.metadata
    stream.properties = {
        "position": 30.0,
        **stream.metadata,
    }
    stream.path = None
    return stream


@pytest.fixture
def mock_stream_2() -> AsyncMock:
    """Create a mock stream."""
    stream = AsyncMock(spec=Snapstream)
    stream.identifier = "test_stream_2"
    stream.status = "idle"
    stream.name = "Test Stream 2"
    stream.friendly_name = "Test Stream 2"
    stream.metadata = None
    stream.meta = None
    stream.properties = None
    stream.path = None
    return stream


@pytest.fixture(
    params=[
        "test_stream_1",
        "test_stream_2",
    ]
)
def stream(request: pytest.FixtureRequest) -> Generator[str]:
    """Return every device."""
    return request.param


@pytest.fixture
def streams(mock_stream_1: AsyncMock, mock_stream_2: AsyncMock) -> dict[str, AsyncMock]:
    """Return a dictionary of mock streams."""
    return {
        mock_stream_1.identifier: mock_stream_1,
        mock_stream_2.identifier: mock_stream_2,
    }
