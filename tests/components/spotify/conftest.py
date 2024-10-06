"""Common test fixtures."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from spotifyaio.models import PlaylistResponse

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.spotify.const import DOMAIN, SPOTIFY_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

SCOPES = " ".join(SPOTIFY_SCOPES)


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
                "scope": SCOPES,
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
                "scope": SCOPES,
                "expires_at": 1724198975.8829377,
            },
            "id": "55oesphrnacjcf7vw5bf6odx3oiu",
            "name": "spotify_account_2",
        },
        unique_id="99fce612f5b8",
        entry_id="32oesphrnacjcf7vw5bf6odx3",
    )


@pytest.fixture
def spotify_mock() -> Generator[MagicMock]:
    """Mock the Spotify API."""
    with patch(
        "homeassistant.components.spotify.SpotifyClient", autospec=True
    ) as spotify_mock:
        spotify_mock.return_value.get_playlists_for_current_user.return_value = (
            PlaylistResponse.from_json(
                load_fixture("current_user_playlists.json", DOMAIN)
            ).items
        )
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
        yield
