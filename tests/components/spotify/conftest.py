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
        # All these fixtures can be retrieved using the Web API client at
        # https://developer.spotify.com/documentation/web-api
        current_user = load_json_value_fixture("current_user.json", DOMAIN)
        client.current_user.return_value = current_user
        client.me.return_value = current_user
        for fixture, method in (
            ("devices.json", "devices"),
            ("current_user_playlist.json", "current_user_playlists"),
            ("playback.json", "current_playback"),
            ("followed_artists.json", "current_user_followed_artists"),
            ("saved_albums.json", "current_user_saved_albums"),
            ("saved_tracks.json", "current_user_saved_tracks"),
            ("saved_shows.json", "current_user_saved_shows"),
            ("recently_played_tracks.json", "current_user_recently_played"),
            ("top_artists.json", "current_user_top_artists"),
            ("top_tracks.json", "current_user_top_tracks"),
            ("featured_playlists.json", "featured_playlists"),
            ("categories.json", "categories"),
            ("category_playlists.json", "category_playlists"),
            ("category.json", "category"),
            ("new_releases.json", "new_releases"),
            ("playlist.json", "playlist"),
            ("album.json", "album"),
            ("artist.json", "artist"),
            ("artist_albums.json", "artist_albums"),
            ("show_episodes.json", "show_episodes"),
            ("show.json", "show"),
        ):
            getattr(client, method).return_value = load_json_value_fixture(
                fixture, DOMAIN
            )
        yield spotify_mock
