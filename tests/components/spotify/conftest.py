"""Common test fixtures."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.spotify import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry_1() -> MockConfigEntry:
    """Mock a config entry with an upper case entry id."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="spotify_1",
        data={
            "auth_implementation": "spotify_c95e4090d4d3438b922331e7428f8171",
            "token": {
                "access_token": "AccessToken",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "RefreshToken",
                "scope": "playlist-read-private ...",
                "expires_at": 1724198975.8829377,
            },
            "id": "32oesphrnacjcf7vw5bf6odx3oiu",
            "name": "spotify_account_1",
        },
        unique_id="84fce612f5b8",
        entry_id="01J5TX5A0FF6G5V0QJX6HBC94T",
    )


@pytest.fixture
def mock_config_entry_2() -> MockConfigEntry:
    """Mock a config entry with a lower case entry id."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="spotify_2",
        data={
            "auth_implementation": "spotify_c95e4090d4d3438b922331e7428f8171",
            "token": {
                "access_token": "AccessToken",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "RefreshToken",
                "scope": "playlist-read-private ...",
                "expires_at": 1724198975.8829377,
            },
            "id": "55oesphrnacjcf7vw5bf6odx3oiu",
            "name": "spotify_account_2",
        },
        unique_id="99fce612f5b8",
        entry_id="32oesphrnacjcf7vw5bf6odx3",
    )


@pytest.fixture
def spotify_playlists() -> dict[str, Any]:
    """Mock the return from getting a list of playlists."""
    return {
        "href": "https://api.spotify.com/v1/users/31oesphrnacjcf7vw5bf6odx3oiu/playlists?offset=0&limit=48",
        "limit": 48,
        "next": None,
        "offset": 0,
        "previous": None,
        "total": 1,
        "items": [
            {
                "collaborative": False,
                "description": "",
                "id": "unique_identifier_00",
                "name": "Playlist1",
                "type": "playlist",
                "uri": "spotify:playlist:unique_identifier_00",
            }
        ],
    }


@pytest.fixture
def spotify_mock(spotify_playlists: dict[str, Any]) -> Generator[MagicMock]:
    """Mock the Spotify API."""
    with patch("homeassistant.components.spotify.Spotify") as spotify_mock:
        mock = MagicMock()
        mock.current_user_playlists.return_value = spotify_playlists
        spotify_mock.return_value = mock
        yield spotify_mock


@pytest.fixture
async def spotify_setup(
    hass: HomeAssistant,
    spotify_mock: MagicMock,
    mock_config_entry_1: MockConfigEntry,
    mock_config_entry_2: MockConfigEntry,
):
    """Set up the spotify integration."""
    with patch(
        "homeassistant.components.spotify.OAuth2Session.async_ensure_token_valid"
    ):
        await async_setup_component(hass, "application_credentials", {})
        await hass.async_block_till_done()
        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential("CLIENT_ID", "CLIENT_SECRET"),
            "spotify_c95e4090d4d3438b922331e7428f8171",
        )
        await hass.async_block_till_done()
        mock_config_entry_1.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_1.entry_id)
        mock_config_entry_2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_2.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done(wait_background_tasks=True)
        yield
