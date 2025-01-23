"""Test the media browser interface."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.media_player import BrowseError
from homeassistant.components.spotify import DOMAIN
from homeassistant.components.spotify.browse_media import async_browse_media
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import SCOPES

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_credentials")
async def test_browse_media_root(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    expires_at: int,
) -> None:
    """Test browsing the root."""
    await setup_integration(hass, mock_config_entry)
    # We add a second config entry to test that lowercase entry_ids also work
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="spotify_2",
        unique_id="second_fake_id",
        data={
            CONF_ID: "second_fake_id",
            "name": "spotify_account_2",
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": SCOPES,
            },
        },
        entry_id="32oesphrnacjcf7vw5bf6odx3",
    )
    await setup_integration(hass, config_entry)
    response = await async_browse_media(hass, None, None)
    assert response.as_dict() == snapshot


@pytest.mark.usefixtures("setup_credentials")
async def test_browse_media_categories(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test browsing categories."""
    await setup_integration(hass, mock_config_entry)
    response = await async_browse_media(
        hass, "spotify://library", f"spotify://{mock_config_entry.entry_id}"
    )
    assert response.as_dict() == snapshot


@pytest.mark.parametrize(
    ("config_entry_id"), [("01J5TX5A0FF6G5V0QJX6HBC94T"), ("32oesphrnacjcf7vw5bf6odx3")]
)
@pytest.mark.usefixtures("setup_credentials")
async def test_browse_media_playlists(
    hass: HomeAssistant,
    config_entry_id: str,
    mock_spotify: MagicMock,
    snapshot: SnapshotAssertion,
    expires_at: int,
) -> None:
    """Test browsing playlists for the two config entries."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Spotify",
        unique_id="1112264649",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": SCOPES,
            },
        },
        entry_id=config_entry_id,
    )
    await setup_integration(hass, mock_config_entry)
    response = await async_browse_media(
        hass,
        "spotify://current_user_playlists",
        f"spotify://{config_entry_id}/current_user_playlists",
    )
    assert response.as_dict() == snapshot


@pytest.mark.parametrize(
    ("media_content_type", "media_content_id"),
    [
        ("current_user_playlists", "current_user_playlists"),
        ("current_user_followed_artists", "current_user_followed_artists"),
        ("current_user_saved_albums", "current_user_saved_albums"),
        ("current_user_saved_tracks", "current_user_saved_tracks"),
        ("current_user_saved_shows", "current_user_saved_shows"),
        ("current_user_recently_played", "current_user_recently_played"),
        ("current_user_top_artists", "current_user_top_artists"),
        ("current_user_top_tracks", "current_user_top_tracks"),
        ("new_releases", "new_releases"),
        ("playlist", "spotify:playlist:3cEYpjA9oz9GiPac4AsH4n"),
        ("album", "spotify:album:3IqzqH6ShrRtie9Yd2ODyG"),
        ("artist", "spotify:artist:0TnOYISbd1XYRBk9myaseg"),
        ("show", "spotify:show:1Y9ExMgMxoBVrgrfU7u0nD"),
    ],
)
@pytest.mark.usefixtures("setup_credentials")
async def test_browsing(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    media_content_type: str,
    media_content_id: str,
) -> None:
    """Test browsing playlists for the two config entries."""
    await setup_integration(hass, mock_config_entry)
    response = await async_browse_media(
        hass,
        f"spotify://{media_content_type}",
        f"spotify://{mock_config_entry.entry_id}/{media_content_id}",
    )
    assert response.as_dict() == snapshot


@pytest.mark.parametrize(
    ("media_content_id"),
    [
        "artist",
        None,
    ],
)
@pytest.mark.usefixtures("setup_credentials")
async def test_invalid_spotify_url(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    media_content_id: str | None,
) -> None:
    """Test browsing with an invalid Spotify URL."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(BrowseError, match="Invalid Spotify URL specified"):
        await async_browse_media(
            hass,
            "spotify://artist",
            media_content_id,
        )


@pytest.mark.usefixtures("setup_credentials")
async def test_browsing_not_loaded_entry(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test browsing with an unloaded config entry."""
    with pytest.raises(BrowseError, match="Invalid Spotify account specified"):
        await async_browse_media(
            hass,
            "spotify://artist",
            f"spotify://{mock_config_entry.entry_id}/spotify:artist:0TnOYISbd1XYRBk9myaseg",
        )
