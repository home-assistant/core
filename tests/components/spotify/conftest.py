"""Common test fixtures."""

from collections.abc import Generator
import time
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.spotify.const import DOMAIN, SPOTIFY_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_value_fixture

SCOPES = " ".join(SPOTIFY_SCOPES)


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(expires_at: int) -> MockConfigEntry:
    """Create Spotify entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="spotify_1",
        unique_id="1112264111",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": SCOPES,
            },
            "id": "1112264111",
            "name": "spotify_account_1",
        },
        entry_id="01J5TX5A0FF6G5V0QJX6HBC94T",
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("CLIENT_ID", "CLIENT_SECRET"),
        DOMAIN,
    )


@pytest.fixture
def mock_spotify() -> Generator[MagicMock]:
    """Mock the Spotify API."""
    with (
        patch(
            "homeassistant.components.spotify.Spotify",
            autospec=True,
        ) as spotify_mock,
        patch(
            "homeassistant.components.spotify.config_flow.Spotify",
            new=spotify_mock,
        ),
    ):
        client = spotify_mock.return_value
        client.current_user_playlists.return_value = load_json_value_fixture(
            "current_user_playlist.json", DOMAIN
        )
        client.current_user.return_value = load_json_value_fixture(
            "current_user.json", DOMAIN
        )
        yield spotify_mock
