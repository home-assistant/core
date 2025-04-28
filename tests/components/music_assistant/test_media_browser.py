"""Test Music Assistant media browser implementation."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.media_player import (
    BrowseError,
    BrowseMedia,
    MediaClass,
    MediaType,
    SearchError,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.components.music_assistant.const import DOMAIN
from homeassistant.components.music_assistant.media_browser import (
    LIBRARY_ALBUMS,
    LIBRARY_ARTISTS,
    LIBRARY_AUDIOBOOKS,
    LIBRARY_PLAYLISTS,
    LIBRARY_PODCASTS,
    LIBRARY_RADIO,
    LIBRARY_TRACKS,
    MEDIA_TYPE_AUDIOBOOK,
    MEDIA_TYPE_RADIO,
    async_browse_media,
    async_search_media,
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


class MockSearchResults:
    """Mock search results."""

    def __init__(self, media_types: list[str]) -> None:
        """Initialize mock search results."""
        self.artists = []
        self.albums = []
        self.tracks = []
        self.playlists = []
        self.radio_stations = []
        self.podcasts = []
        self.audiobooks = []

        # Create mock items based on requested media types
        for media_type in media_types:
            items = []
            for i in range(5):  # Create 5 mock items for each type
                item = MagicMock()
                item.name = f"Test {media_type} {i}"
                item.uri = f"library://{media_type}/{i}"
                item.available = True
                item.artists = []
                media_type_mock = MagicMock()
                media_type_mock.value = media_type
                item.media_type = media_type_mock
                items.append(item)

            # Assign to the appropriate attribute
            if media_type == "artist":
                self.artists = items
            elif media_type == "album":
                self.albums = items
            elif media_type == "track":
                self.tracks = items
            elif media_type == "playlist":
                self.playlists = items
            elif media_type == "radio":
                self.radio_stations = items
            elif media_type == "podcast":
                self.podcasts = items
            elif media_type == "audiobook":
                self.audiobooks = items


@pytest.mark.parametrize(
    ("search_query", "media_content_type", "expected_items"),
    [
        # Search for tracks
        ("track", MediaType.TRACK, 5),
        # Search for albums
        ("album", MediaType.ALBUM, 5),
        # Search for artists
        ("artist", MediaType.ARTIST, 5),
        # Search for playlists
        ("playlist", MediaType.PLAYLIST, 5),
        # Search for radio stations
        ("radio", MEDIA_TYPE_RADIO, 5),
        # Search for podcasts
        ("podcast", MediaType.PODCAST, 5),
        # Search for audiobooks
        ("audiobook", MEDIA_TYPE_AUDIOBOOK, 5),
        # Search with no media type specified (should return all types)
        ("music", None, 35),
    ],
)
async def test_search_media(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    search_query: str,
    media_content_type: str,
    expected_items: int,
) -> None:
    """Test the async_search_media method with different content types."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    # Create mock search results
    media_types = []
    if media_content_type == MediaType.TRACK:
        media_types = ["track"]
    elif media_content_type == MediaType.ALBUM:
        media_types = ["album"]
    elif media_content_type == MediaType.ARTIST:
        media_types = ["artist"]
    elif media_content_type == MediaType.PLAYLIST:
        media_types = ["playlist"]
    elif media_content_type == MEDIA_TYPE_RADIO:
        media_types = ["radio"]
    elif media_content_type == MediaType.PODCAST:
        media_types = ["podcast"]
    elif media_content_type == MEDIA_TYPE_AUDIOBOOK:
        media_types = ["audiobook"]
    elif media_content_type is None:
        media_types = [
            "artist",
            "album",
            "track",
            "playlist",
            "radio",
            "podcast",
            "audiobook",
        ]

    mock_results = MockSearchResults(media_types)

    # Use patch instead of trying to mock return_value
    with patch.object(
        music_assistant_client.music, "search", return_value=mock_results
    ):
        # Create search query
        query = SearchMediaQuery(
            search_query=search_query,
            media_content_type=media_content_type,
        )

        # Perform search
        search_results = await async_search_media(music_assistant_client, query)

        # Verify search results
        assert isinstance(search_results, SearchMedia)

        if media_content_type is not None:
            # For specific media types, expect up to 5 results
            assert len(search_results.result) <= 5
        else:
            # For "all types" search, we'd expect items from each type
            # But since we're returning exactly 5 items per type (from mock)
            # we'd expect 5 * 7 = 35 items maximum
            assert len(search_results.result) <= 35


@pytest.mark.parametrize(
    ("search_query", "media_filter_classes", "expected_media_types"),
    [
        # Search for tracks
        ("track", {MediaClass.TRACK}, ["track"]),
        # Search for albums
        ("album", {MediaClass.ALBUM}, ["album"]),
        # Search for artists
        ("artist", {MediaClass.ARTIST}, ["artist"]),
        # Search for playlists
        ("playlist", {MediaClass.PLAYLIST}, ["playlist"]),
        # Search for multiple media classes
        ("music", {MediaClass.ALBUM, MediaClass.TRACK}, ["album", "track"]),
    ],
)
async def test_search_media_with_filter_classes(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    search_query: str,
    media_filter_classes: set[MediaClass],
    expected_media_types: list[str],
) -> None:
    """Test the async_search_media method with different media filter classes."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    # Create mock search results
    mock_results = MockSearchResults(expected_media_types)

    # Use patch instead of trying to mock return_value directly
    with patch.object(
        music_assistant_client.music, "search", return_value=mock_results
    ):
        # Create search query
        query = SearchMediaQuery(
            search_query=search_query,
            media_filter_classes=media_filter_classes,
        )

        # Perform search
        search_results = await async_search_media(music_assistant_client, query)

        # Verify search results
        assert isinstance(search_results, SearchMedia)
        expected_items = len(expected_media_types) * 5  # 5 items per media type
        assert len(search_results.result) <= expected_items


async def test_search_media_within_album(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test searching within an album context."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    # Mock album and tracks
    album = MagicMock()
    album.item_id = "396"
    album.provider = "library"

    tracks = []
    for i in range(5):
        track = MagicMock()
        track.name = f"Test Track {i}"
        track.uri = f"library://track/{i}"
        track.available = True
        track.artists = []
        media_type_mock = MagicMock()
        media_type_mock.value = "track"
        track.media_type = media_type_mock
        tracks.append(track)

    # Set up mocks using patch
    with (
        patch.object(
            music_assistant_client.music, "get_item_by_uri", return_value=album
        ),
        patch.object(
            music_assistant_client.music, "get_album_tracks", return_value=tracks
        ),
    ):
        # Create search query within an album
        album_uri = "library://album/396"
        query = SearchMediaQuery(
            search_query="track",
            media_content_id=album_uri,
        )

        # Perform search
        search_results = await async_search_media(music_assistant_client, query)

        # Verify search results
        assert isinstance(search_results, SearchMedia)
        assert len(search_results.result) > 0  # Should have results


async def test_search_media_error(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that search errors are properly handled."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    # Use patch to cause an exception
    with patch.object(
        music_assistant_client.music, "search", side_effect=Exception("Search failed")
    ):
        # Create search query
        query = SearchMediaQuery(
            search_query="error test",
        )

        # Verify that the error is caught and a SearchError is raised
        with pytest.raises(SearchError, match="Error searching for error test"):
            await async_search_media(music_assistant_client, query)
