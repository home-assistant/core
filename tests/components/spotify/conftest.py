"""Common test fixtures."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

import pytest
from spotifyaio.models import (
    Album,
    Artist,
    ArtistResponse,
    AudioFeatures,
    CategoriesResponse,
    Category,
    CategoryPlaylistResponse,
    Devices,
    FeaturedPlaylistResponse,
    NewReleasesResponse,
    NewReleasesResponseInner,
    PlaybackState,
    PlayedTrackResponse,
    Playlist,
    PlaylistResponse,
    SavedAlbumResponse,
    SavedShowResponse,
    SavedTrackResponse,
    Show,
    ShowEpisodesResponse,
    TopArtistsResponse,
    TopTracksResponse,
    UserProfile,
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.spotify.const import DOMAIN, SPOTIFY_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

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


@pytest.fixture(autouse=True)
async def patch_sleep() -> Generator[AsyncMock]:
    """Fixture to setup credentials."""
    with patch("homeassistant.components.spotify.media_player.AFTER_REQUEST_SLEEP", 0):
        yield


@pytest.fixture
def mock_spotify() -> Generator[AsyncMock]:
    """Mock the Spotify API."""
    with (
        patch(
            "homeassistant.components.spotify.SpotifyClient", autospec=True
        ) as spotify_mock,
        patch(
            "homeassistant.components.spotify.config_flow.SpotifyClient",
            new=spotify_mock,
        ),
    ):
        client = spotify_mock.return_value
        # All these fixtures can be retrieved using the Web API client at
        # https://developer.spotify.com/documentation/web-api
        for fixture, method, obj in (
            (
                "current_user_playlist.json",
                "get_playlists_for_current_user",
                PlaylistResponse,
            ),
            ("saved_albums.json", "get_saved_albums", SavedAlbumResponse),
            ("saved_tracks.json", "get_saved_tracks", SavedTrackResponse),
            ("saved_shows.json", "get_saved_shows", SavedShowResponse),
            (
                "recently_played_tracks.json",
                "get_recently_played_tracks",
                PlayedTrackResponse,
            ),
            ("top_artists.json", "get_top_artists", TopArtistsResponse),
            ("top_tracks.json", "get_top_tracks", TopTracksResponse),
            ("show_episodes.json", "get_show_episodes", ShowEpisodesResponse),
            ("artist_albums.json", "get_artist_albums", NewReleasesResponseInner),
        ):
            getattr(client, method).return_value = obj.from_json(
                load_fixture(fixture, DOMAIN)
            ).items
        for fixture, method, obj in (
            (
                "playback.json",
                "get_playback",
                PlaybackState,
            ),
            ("current_user.json", "get_current_user", UserProfile),
            ("category.json", "get_category", Category),
            ("playlist.json", "get_playlist", Playlist),
            ("album.json", "get_album", Album),
            ("artist.json", "get_artist", Artist),
            ("show.json", "get_show", Show),
            ("audio_features.json", "get_audio_features", AudioFeatures),
        ):
            getattr(client, method).return_value = obj.from_json(
                load_fixture(fixture, DOMAIN)
            )
        client.get_followed_artists.return_value = ArtistResponse.from_json(
            load_fixture("followed_artists.json", DOMAIN)
        ).artists.items
        client.get_featured_playlists.return_value = FeaturedPlaylistResponse.from_json(
            load_fixture("featured_playlists.json", DOMAIN)
        ).playlists.items
        client.get_categories.return_value = CategoriesResponse.from_json(
            load_fixture("categories.json", DOMAIN)
        ).categories.items
        client.get_category_playlists.return_value = CategoryPlaylistResponse.from_json(
            load_fixture("category_playlists.json", DOMAIN)
        ).playlists.items
        client.get_new_releases.return_value = NewReleasesResponse.from_json(
            load_fixture("new_releases.json", DOMAIN)
        ).albums.items
        client.get_devices.return_value = Devices.from_json(
            load_fixture("devices.json", DOMAIN)
        ).devices
        yield spotify_mock
