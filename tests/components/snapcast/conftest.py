"""Test the snapcast config flow."""

from collections.abc import Generator, Mapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from snapcast.control.server import CONTROL_PORT

from homeassistant.components.snapcast.const import DOMAIN
from homeassistant.components.snapcast.coordinator import Snapserver
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.snapcast.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_create_server() -> Generator[AsyncMock]:
    """Create mock snapcast connection."""
    mock_connection = AsyncMock()
    mock_connection.start = AsyncMock(return_value=None)
    mock_connection.stop = MagicMock()
    with patch("snapcast.control.create_server", return_value=mock_connection):
        yield mock_connection


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
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
def mock_server_connection() -> Generator[Snapserver]:
    """Create a mock server connection."""

    # Patch the start method of the Snapserver class to avoid network connections
    with patch.object(Snapserver, "start", new_callable=AsyncMock) as mock_start:
        yield mock_start


@pytest.fixture
def mock_server_state() -> Mapping[str, Any]:
    """Create a mock server state."""
    return {
        "server": {
            "server": {
                "snapserver": {
                    "controlProtocolVersion": 1,
                    "name": "Snapserver",
                    "protocolVersion": 1,
                    "version": "0.10.0",
                },
            },
            "groups": [
                {
                    "clients": [
                        {
                            "id": "00:21:6a:7d:74:fc#2",
                            "connected": True,
                            "lastSeen": {"sec": 1488025751, "usec": 654777},
                            "config": {
                                "instance": 2,
                                "latency": 6,
                                "name": "test_client",
                                "volume": {"muted": False, "percent": 48},
                            },
                            "snapclient": {
                                "name": "Snapclient",
                                "protocolVersion": 2,
                                "version": "0.10.0",
                            },
                        }
                    ],
                    "id": "4dcc4e3b-c699-a04b-7f0c-8260d23c43e1",
                    "muted": False,
                    "name": "test_group",
                    "stream_id": "test_stream_1",
                }
            ],
            "streams": [
                {
                    "id": "test_stream_1",
                    "status": "playing",
                    "uri": {
                        "fragment": "",
                        "host": "",
                        "query": {
                            "chunk_ms": "20",
                            "codec": "flac",
                            "name": "Test Stream 1",
                            "sampleformat": "48000:16:2",
                        },
                        "scheme": "pipe",
                    },
                    "properties": {
                        "position": 30.0,
                        "metadata": {
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
                        },
                    },
                },
                {
                    "id": "test_stream_2",
                    "status": "idle",
                    "uri": {
                        "fragment": "",
                        "host": "",
                        "query": {
                            "chunk_ms": "20",
                            "codec": "flac",
                            "name": "Test Stream 2",
                            "sampleformat": "48000:16:2",
                        },
                        "scheme": "pipe",
                    },
                },
            ],
        }
    }
