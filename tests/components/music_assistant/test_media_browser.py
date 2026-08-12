"""Test Music Assistant media browser implementation."""

from unittest.mock import MagicMock, patch

from music_assistant_models.enums import MediaType as MASSMediaType
from music_assistant_models.media_items import SearchResults
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

from tests.typing import WebSocketGenerator


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
        self.radio = []
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
                self.radio = items
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


async def test_search_media_within_playlist(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test searching within a playlist context."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    playlist = MagicMock()
    playlist.item_id = "40"
    playlist.provider = "library"

    with (
        patch.object(
            music_assistant_client.music, "get_item_by_uri", return_value=playlist
        ),
        patch.object(music_assistant_client.music, "search") as mock_search,
    ):
        query = SearchMediaQuery(
            search_query="fooled",
            media_content_id="library://playlist/40",
        )
        search_results = await async_search_media(music_assistant_client, query)

    # the playlist tracks are filtered locally, without hitting the search api
    mock_search.assert_not_called()
    assert [item.title for item in search_results.result] == [
        "The Who - Won't Get Fooled Again"
    ]


@pytest.mark.parametrize(
    ("media_content_id", "expected_media_type"),
    [
        (LIBRARY_ARTISTS, MASSMediaType.ARTIST),
        (LIBRARY_ALBUMS, MASSMediaType.ALBUM),
        (LIBRARY_TRACKS, MASSMediaType.TRACK),
        (LIBRARY_PLAYLISTS, MASSMediaType.PLAYLIST),
        (LIBRARY_RADIO, MASSMediaType.RADIO),
        (LIBRARY_PODCASTS, MASSMediaType.PODCAST),
        (LIBRARY_AUDIOBOOKS, MASSMediaType.AUDIOBOOK),
    ],
)
async def test_search_media_scoped_to_library(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_content_id: str,
    expected_media_type: MASSMediaType,
) -> None:
    """Test that searching from a library listing only searches that library.

    The browse tree reports the library listings as our own domain instead of a
    concrete media type, so the listing id is what scopes the search.
    """
    await setup_integration_from_fixtures(hass, music_assistant_client)

    mock_results = MockSearchResults([expected_media_type.value])

    with patch.object(
        music_assistant_client.music, "search", return_value=mock_results
    ) as mock_search:
        query = SearchMediaQuery(
            search_query="test",
            media_content_type=DOMAIN,
            media_content_id=media_content_id,
        )
        search_results = await async_search_media(music_assistant_client, query)

    assert mock_search.call_args.kwargs["media_types"] == [expected_media_type]
    assert len(search_results.result) == 5


@pytest.mark.parametrize(
    ("media_content_id", "media_content_type"),
    [
        (LIBRARY_ARTISTS, MediaType.ARTIST),
        (LIBRARY_ALBUMS, MediaType.ALBUM),
        (LIBRARY_TRACKS, MediaType.TRACK),
        (LIBRARY_PLAYLISTS, MediaType.PLAYLIST),
        (LIBRARY_RADIO, DOMAIN),
        (LIBRARY_PODCASTS, MediaType.PODCAST),
        (LIBRARY_AUDIOBOOKS, DOMAIN),
        ("artist", MediaType.ARTIST),
        ("album", MediaType.ALBUM),
        ("playlist", DOMAIN),
    ],
)
async def test_browse_media_can_search(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_content_id: str,
    media_content_type: str,
) -> None:
    """Test that browse listings tell the media browser they can be searched."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    browse_item = await async_browse_media(
        hass, music_assistant_client, media_content_id, media_content_type
    )

    assert browse_item.can_search is True


async def test_browse_media_root_cannot_search(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that the root listing does not offer search."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    browse_item = await async_browse_media(hass, music_assistant_client, None, None)

    assert browse_item.can_search is False


async def test_browse_artist_search_media_classes(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that an artist listing offers its searchable media classes."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    browse_item = await async_browse_media(
        hass, music_assistant_client, "artist", MediaType.ARTIST
    )

    assert browse_item.search_media_classes == [MediaClass.ALBUM, MediaClass.TRACK]


@pytest.mark.parametrize(
    "media_content_type",
    [MediaType.MUSIC, MediaType.ARTIST, None],
)
async def test_search_within_artist_ignores_surrounding_media_type(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_content_type: str | None,
) -> None:
    """Test that an artist search returns its albums and tracks either way.

    An artist holds no artists, so a surrounding artist media type must not be
    taken as the thing to look for, or the whole response gets discarded.
    """
    await setup_integration_from_fixtures(hass, music_assistant_client)

    artist = MagicMock()
    artist.name = "Test Artist"
    mock = MockSearchResults(["album", "track"])

    with (
        patch.object(
            music_assistant_client.music, "get_item_by_uri", return_value=artist
        ),
        patch.object(
            music_assistant_client.music,
            "search",
            return_value=SearchResults(albums=mock.albums, tracks=mock.tracks),
        ) as mock_search,
    ):
        search_results = await async_search_media(
            music_assistant_client,
            SearchMediaQuery(
                search_query="test",
                media_content_type=media_content_type,
                media_content_id="library://artist/127",
            ),
        )

    assert mock_search.call_args.kwargs["media_types"] == [
        MASSMediaType.ALBUM,
        MASSMediaType.TRACK,
    ]
    assert {item.media_class for item in search_results.result} == {
        MediaClass.ALBUM,
        MediaClass.TRACK,
    }


@pytest.mark.parametrize(
    "media_content_type",
    [MediaType.MUSIC, MediaType.ARTIST],
)
@pytest.mark.parametrize(
    ("media_filter_classes", "expected_media_types", "expected_classes"),
    [
        (
            None,
            [MASSMediaType.ALBUM, MASSMediaType.TRACK],
            {MediaClass.ALBUM, MediaClass.TRACK},
        ),
        ({MediaClass.ALBUM}, [MASSMediaType.ALBUM], {MediaClass.ALBUM}),
        ({MediaClass.TRACK}, [MASSMediaType.TRACK], {MediaClass.TRACK}),
    ],
)
async def test_search_within_artist_with_filter_classes(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_content_type: str,
    media_filter_classes: set[MediaClass] | None,
    expected_media_types: list[MASSMediaType],
    expected_classes: set[MediaClass],
) -> None:
    """Test that the filters offered on an artist listing narrow its results.

    A filter is picked by the user, so it has to win from whatever media type
    happens to surround the search.
    """
    await setup_integration_from_fixtures(hass, music_assistant_client)

    artist = MagicMock()
    artist.name = "Test Artist"
    mock = MockSearchResults(["album", "track"])

    with (
        patch.object(
            music_assistant_client.music, "get_item_by_uri", return_value=artist
        ),
        patch.object(
            music_assistant_client.music,
            "search",
            return_value=SearchResults(albums=mock.albums, tracks=mock.tracks),
        ) as mock_search,
    ):
        search_results = await async_search_media(
            music_assistant_client,
            SearchMediaQuery(
                search_query="test",
                media_content_type=media_content_type,
                media_content_id="library://artist/127",
                media_filter_classes=media_filter_classes,
            ),
        )

    # the artist name scopes the query that is sent to the search api
    assert mock_search.call_args.args[0] == "Test Artist - test"
    # a filter narrows what we ask for, instead of asking for everything
    # an artist can hold and dropping most of the response again
    assert mock_search.call_args.kwargs["media_types"] == expected_media_types
    assert {item.media_class for item in search_results.result} == expected_classes


@pytest.mark.parametrize(
    ("media_content_id", "expected_media_types"),
    [
        (
            None,
            [
                MASSMediaType.ARTIST,
                MASSMediaType.ALBUM,
                MASSMediaType.TRACK,
                MASSMediaType.PLAYLIST,
            ],
        ),
        # inside an artist there is no more music to be had than their own
        ("library://artist/127", [MASSMediaType.ALBUM, MASSMediaType.TRACK]),
    ],
)
async def test_search_media_music_class_searches_music(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_content_id: str | None,
    expected_media_types: list[MASSMediaType],
) -> None:
    """Test that asking for music searches music instead of radio.

    A voice assistant sends this class for a plain "play something" request,
    and we hand radio stations back to HA under the same class, which is why
    it used to end up searching radio only.
    """
    await setup_integration_from_fixtures(hass, music_assistant_client)

    artist = MagicMock()
    artist.name = "Test Artist"
    mock = MockSearchResults(["artist", "album", "track", "playlist"])

    with (
        patch.object(
            music_assistant_client.music, "get_item_by_uri", return_value=artist
        ),
        patch.object(
            music_assistant_client.music,
            "search",
            return_value=SearchResults(
                artists=mock.artists,
                albums=mock.albums,
                tracks=mock.tracks,
                playlists=mock.playlists,
            ),
        ) as mock_search,
    ):
        search_results = await async_search_media(
            music_assistant_client,
            SearchMediaQuery(
                search_query="some artist",
                media_content_id=media_content_id,
                media_filter_classes={MediaClass.MUSIC},
            ),
        )

    assert mock_search.call_args.kwargs["media_types"] == expected_media_types
    assert search_results.result


@pytest.mark.parametrize(
    ("media_content_id", "media_filter_classes"),
    [
        # an artist holds no playlists, so there is nothing to find
        ("library://artist/127", {MediaClass.PLAYLIST}),
        # nothing we can search for is an image
        ("library://artist/127", {MediaClass.IMAGE}),
        (None, {MediaClass.IMAGE}),
    ],
)
async def test_search_media_with_unsearchable_filter(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_content_id: str | None,
    media_filter_classes: set[MediaClass],
) -> None:
    """Test that a filter we cannot honour returns nothing, not everything."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    with patch.object(music_assistant_client.music, "search") as mock_search:
        search_results = await async_search_media(
            music_assistant_client,
            SearchMediaQuery(
                search_query="test",
                media_content_id=media_content_id,
                media_filter_classes=media_filter_classes,
            ),
        )

    mock_search.assert_not_called()
    assert search_results.result == []


async def test_search_media_results_are_browsable(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
) -> None:
    """Test that every expandable search result can actually be browsed."""
    await setup_integration_from_fixtures(hass, music_assistant_client)

    media_types = ["artist", "album", "track", "playlist", "radio", "podcast"]
    mock = MockSearchResults(media_types)
    results = SearchResults(
        artists=mock.artists,
        albums=mock.albums,
        tracks=mock.tracks,
        playlists=mock.playlists,
        radio=mock.radio,
        podcasts=mock.podcasts,
    )

    with patch.object(music_assistant_client.music, "search", return_value=results):
        search_results = await async_search_media(
            music_assistant_client, SearchMediaQuery(search_query="test")
        )

    expandable = [item for item in search_results.result if item.can_expand]
    assert expandable
    for item in expandable:
        # raises BrowseError if the browse tree has no route for this item
        await async_browse_media(
            hass, music_assistant_client, item.media_content_id, item.media_content_type
        )


async def test_search_media_websocket_from_library_listing(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test searching a library listing the way the media browser does.

    The media browser reports the listing as the child that its parent built, so
    it sends our domain as the content type and the listing id as the content id.
    """
    await setup_integration_from_fixtures(hass, music_assistant_client)

    root = await async_browse_media(hass, music_assistant_client, None, None)
    artists_child = next(
        child for child in root.children if child.media_content_id == LIBRARY_ARTISTS
    )
    listing = await async_browse_media(
        hass,
        music_assistant_client,
        artists_child.media_content_id,
        artists_child.media_content_type,
    )
    assert listing.can_search is True

    client = await hass_ws_client(hass)
    with patch.object(
        music_assistant_client.music,
        "search",
        return_value=MockSearchResults(["artist"]),
    ) as mock_search:
        await client.send_json_auto_id(
            {
                "type": "media_player/search_media",
                "entity_id": "media_player.test_player_1",
                "search_query": "test",
                "media_content_id": artists_child.media_content_id,
                "media_content_type": artists_child.media_content_type,
            }
        )
        msg = await client.receive_json()

    assert msg["success"]
    assert mock_search.call_args.kwargs["media_types"] == [MASSMediaType.ARTIST]
    assert len(msg["result"]["result"]) == 5
    assert all(item["media_class"] == "artist" for item in msg["result"]["result"])


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
