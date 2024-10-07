"""Test the media browser interface."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

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
