"""Test Music Assistant media browser implementation."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.media_player import BrowseError, BrowseMedia, MediaType
from homeassistant.components.music_assistant.const import DOMAIN
from homeassistant.components.music_assistant.media_browser import (
    LIBRARY_ALBUMS,
    LIBRARY_ARTISTS,
    LIBRARY_AUDIOBOOKS,
    LIBRARY_PLAYLISTS,
    LIBRARY_PODCASTS,
    LIBRARY_RADIO,
    LIBRARY_TRACKS,
    async_browse_media,
)
from homeassistant.core import HomeAssistant

from .common import setup_integration_from_fixtures


@pytest.mark.parametrize(
    ("media_content_id", "media_content_type", "expected"),
    [
        (LIBRARY_PLAYLISTS, MediaType.PLAYLIST, "library://playlist/40"),
        (LIBRARY_ARTISTS, MediaType.ARTIST, "library://artist/127"),
        (LIBRARY_ALBUMS, MediaType.ALBUM, "library://album/396"),
        (LIBRARY_TRACKS, MediaType.TRACK, "library://track/456"),
        (LIBRARY_RADIO, DOMAIN, "library://radio/1"),
        (LIBRARY_PODCASTS, MediaType.PODCAST, "library://podcast/6"),
        (LIBRARY_AUDIOBOOKS, DOMAIN, "library://audiobook/1"),
        ("artist", MediaType.ARTIST, "library://album/115"),
        ("album", MediaType.ALBUM, "library://track/247"),
        ("playlist", DOMAIN, "tidal--Ah76MuMg://track/77616130"),
        (None, None, "artists"),
    ],
)
async def test_browse_media_root(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_content_id: str,
    media_content_type: str,
    expected: str,
) -> None:
    """Test the async_browse_media method."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    state = hass.states.get(entity_id)
    assert state
    browse_item: BrowseMedia = await async_browse_media(
        hass, music_assistant_client, media_content_id, media_content_type
    )
    assert browse_item.children[0].media_content_id == expected


async def test_browse_media_not_found(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test the async_browse_media method when media is not found."""
    await setup_integration_from_fixtures(hass, music_assistant_client)
    entity_id = "media_player.test_player_1"
    state = hass.states.get(entity_id)
    assert state

    with pytest.raises(BrowseError, match="Media not found: unknown / unknown"):
        await async_browse_media(hass, music_assistant_client, "unknown", "unknown")
