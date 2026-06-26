"""Fixtures for the HiFiBerry tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hifiberry.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.hifiberry.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "hifiberry.local", CONF_PORT: DEFAULT_PORT},
        title="Kitchen Speaker",
        unique_id="hifiberry.local",
        version=2,
    )


@pytest.fixture
def mock_audiocontrol_client() -> Generator[MagicMock]:
    """Patch AudioControlClient and return the mocked instance."""
    with (
        patch(
            "homeassistant.components.hifiberry.AudioControlClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.hifiberry.config_flow.AudioControlClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_validate = AsyncMock()
        client.async_update = AsyncMock()
        client.async_command = AsyncMock()
        client.async_set_volume = AsyncMock()
        client.async_volume_up = AsyncMock()
        client.async_volume_down = AsyncMock()
        client.connected = True
        client.base_url = "http://hifiberry.local:80"
        client.public_base_url = "http://hifiberry.local"
        client.now_playing = {
            "state": "playing",
            "player": {
                "name": "spotify",
                "state": "playing",
                "capabilities": ["play", "pause", "stop", "next", "previous"],
            },
            "song": {
                "title": "Big Love",
                "artist": "Fleetwood Mac",
                "album": "Greatest Hits",
            },
        }
        client.volume = {"percentage": 80}
        client.cover_art_url = "https://example.com/cover.jpg"
        client.active_player_name = "spotify"
        client.last_active_player_name = "spotify"
        client.active_player_capabilities = {
            "play",
            "pause",
            "stop",
            "next",
            "previous",
        }
        yield client
