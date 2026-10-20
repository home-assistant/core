"""Tests for Plex server."""

from types import SimpleNamespace
from unittest.mock import patch

from plexapi.exceptions import BadRequest, NotFound
import pytest
import requests_mock

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.components.plex.const import DOMAIN
from homeassistant.components.plex.errors import MediaNotFound
from homeassistant.components.plex.media_search import (
    fuzzy_search,
    normalize_title,
    title_score,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_media_lookups(
    hass: HomeAssistant,
    mock_plex_server,
    requests_mock: requests_mock.Mocker,
    playqueue_created,
) -> None:
    """Test media lookups to Plex server."""
    # Plex Key searches
    media_player_id = hass.states.async_entity_ids("media_player")[0]
    requests_mock.post("/playqueues", text=playqueue_created)
    requests_mock.get("/player/playback/playMedia", status_code=200)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player_id,
            ATTR_MEDIA_CONTENT_TYPE: DOMAIN,
            ATTR_MEDIA_CONTENT_ID: 1,
        },
        True,
    )
    with (
        pytest.raises(MediaNotFound) as excinfo,
        patch("plexapi.server.PlexServer.fetchItem", side_effect=NotFound),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: DOMAIN,
                ATTR_MEDIA_CONTENT_ID: 123,
            },
            True,
        )
    assert "Media for key 123 not found" in str(excinfo.value)

    # Search with a different specified username
    with (
        patch(
            "plexapi.library.LibrarySection.search",
            __qualname__="search",
        ) as search,
        patch(
            "plexapi.myplex.MyPlexAccount.user",
            __qualname__="user",
        ) as plex_account_user,
    ):
        plex_account_user.return_value.get_token.return_value = "token"
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "TV Shows",'
                    ' "show_name": "TV Show",'
                    ' "username": "Kids"}'
                ),
            },
            True,
        )
        search.assert_called_with(**{"show.title": "TV Show", "libtype": "show"})
        plex_account_user.assert_called_with("Kids")

    # TV show searches
    with pytest.raises(MediaNotFound) as excinfo:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "Not a Library", "show_name": "TV Show"}'
                ),
            },
            True,
        )
    assert "Library 'Not a Library' not found in" in str(excinfo.value)

    with patch(
        "plexapi.library.LibrarySection.search",
        __qualname__="search",
    ) as search:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "TV Shows", "show_name": "TV Show"}'
                ),
            },
            True,
        )
        search.assert_called_with(**{"show.title": "TV Show", "libtype": "show"})

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "TV Shows", "episode_name": "An Episode"}'
                ),
            },
            True,
        )
        search.assert_called_with(
            **{"episode.title": "An Episode", "libtype": "episode"}
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "TV Shows",'
                    ' "show_name": "TV Show",'
                    ' "season_number": 1}'
                ),
            },
            True,
        )
        search.assert_called_with(
            **{"show.title": "TV Show", "season.index": 1, "libtype": "season"}
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.EPISODE,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "TV Shows",'
                    ' "show_name": "TV Show",'
                    ' "season_number": 1,'
                    ' "episode_number": 3}'
                ),
            },
            True,
        )
        search.assert_called_with(
            **{
                "show.title": "TV Show",
                "season.index": 1,
                "episode.index": 3,
                "libtype": "episode",
            }
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "Music", "artist_name": "Artist"}'
                ),
            },
            True,
        )
        search.assert_called_with(**{"artist.title": "Artist", "libtype": "artist"})

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "Music", "album_name": "Album"}'
                ),
            },
            True,
        )
        search.assert_called_with(**{"album.title": "Album", "libtype": "album"})

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "Music",'
                    ' "artist_name": "Artist",'
                    ' "track_name": "Track 3"}'
                ),
            },
            True,
        )
        search.assert_called_with(
            **{"artist.title": "Artist", "track.title": "Track 3", "libtype": "track"}
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "Music",'
                    ' "artist_name": "Artist",'
                    ' "album_name": "Album"}'
                ),
            },
            True,
        )
        search.assert_called_with(
            **{"artist.title": "Artist", "album.title": "Album", "libtype": "album"}
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "Music",'
                    ' "artist_name": "Artist",'
                    ' "album_name": "Album",'
                    ' "track_number": 3}'
                ),
            },
            True,
        )
        search.assert_called_with(
            **{
                "artist.title": "Artist",
                "album.title": "Album",
                "track.index": 3,
                "libtype": "track",
            }
        )

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "Music",'
                    ' "artist_name": "Artist",'
                    ' "album_name": "Album",'
                    ' "track_name": "Track 3"}'
                ),
            },
            True,
        )
        search.assert_called_with(
            **{
                "artist.title": "Artist",
                "album.title": "Album",
                "track.title": "Track 3",
                "libtype": "track",
            }
        )

        # Movie searches
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.VIDEO,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "Movies", "video_name": "Movie 1"}'
                ),
            },
            True,
        )
        search.assert_called_with(**{"movie.title": "Movie 1", "libtype": None})

        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MOVIE,
                ATTR_MEDIA_CONTENT_ID: '{"library_name": "Movies", "title": "Movie 1"}',
            },
            True,
        )
        search.assert_called_with(title="Movie 1", libtype=None)

    with pytest.raises(MediaNotFound) as excinfo:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.VIDEO,
                ATTR_MEDIA_CONTENT_ID: '{"title": "Movie 1"}',
            },
            True,
        )
    assert "Must specify 'library_name' for this search" in str(excinfo.value)

    with (
        pytest.raises(MediaNotFound) as excinfo,
        patch(
            "plexapi.library.LibrarySection.search",
            side_effect=BadRequest,
            __qualname__="search",
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.VIDEO,
                ATTR_MEDIA_CONTENT_ID: (
                    '{"library_name": "Movies", "title": "Not a Movie"}'
                ),
            },
            True,
        )
    assert "Problem in query" in str(excinfo.value)

    # Playlist searches
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player_id,
            ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
            ATTR_MEDIA_CONTENT_ID: '{"playlist_name": "Playlist 1"}',
        },
        True,
    )

    with pytest.raises(MediaNotFound) as excinfo:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
                ATTR_MEDIA_CONTENT_ID: '{"playlist_name": "Not a Playlist"}',
            },
            True,
        )
    assert "Playlist 'Not a Playlist' not found" in str(excinfo.value)

    with pytest.raises(MediaNotFound) as excinfo:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.PLAYLIST,
                ATTR_MEDIA_CONTENT_ID: "{}",
            },
            True,
        )
    assert "Must specify 'playlist_name' for this search" in str(excinfo.value)


def test_title_score_keeps_non_latin_titles() -> None:
    """Test titles in other scripts are compared and not reduced to nothing."""
    query = normalize_title("Шерлок")
    assert query == "шерлок"
    assert title_score(query, "Шерлок") == 1.0
    assert title_score(query, "Шерлок Холмс") > title_score(query, "Мастер")
    assert normalize_title("Amélie") == "amelie"


def test_title_score_ignores_word_order() -> None:
    """Test a title is found when the words are said in another order."""
    query = normalize_title("Reloaded Matrix")
    assert title_score(query, "Matrix Reloaded") > 0.9
    assert title_score(query, "Inception") < 0.6


def test_title_score_finds_titles_that_sound_alike() -> None:
    """Test misspelled titles that sound the same are found."""
    assert title_score(normalize_title("cary"), "Carrie") > 0.9
    assert title_score(normalize_title("fone booth"), "Phone Booth") > 0.9
    assert title_score(normalize_title("avatar"), "Inception") < 0.6


def test_normalize_title_folds_letters() -> None:
    """Test letters without an accented form are turned into plain letters."""
    assert normalize_title("Ørnen") == "ornen"
    assert normalize_title("Straße") == "strasse"
    assert title_score(normalize_title("ornen"), "Ørnen") == 1.0
    assert title_score(normalize_title("gooise vrouwen"), "Gooische Vrouwen") > 0.8


def _media(title: str, rating_key: int, media_type: str) -> SimpleNamespace:
    """Return a stand-in for a Plex media item."""
    return SimpleNamespace(title=title, ratingKey=rating_key, type=media_type)


def _section(
    section_type: str, native: list, items_by_type: dict, calls: list
) -> SimpleNamespace:
    """Return a stand-in for a Plex library."""

    def search(**kwargs):
        calls.append(kwargs)
        if "title" in kwargs:
            return native
        return items_by_type.get(kwargs.get("libtype"), [])

    return SimpleNamespace(type=section_type, search=search)


def _server(sections=(), playlists=(), native=()) -> SimpleNamespace:
    """Return a stand-in for a Plex server."""
    return SimpleNamespace(
        search=lambda query, mediatype=None: list(native),
        playlists=lambda: list(playlists),
        library=SimpleNamespace(sections=lambda: list(sections)),
    )


def test_title_score_ignores_titles_without_sound() -> None:
    """Test unrelated titles without a sound key do not match each other."""
    assert title_score(normalize_title("шерлок холмс"), "Игра престолов") < 0.6
    assert title_score(normalize_title("12 34"), "56 78") < 0.6


def test_fuzzy_search_finds_playlists() -> None:
    """Test misspelled playlists are found, but not in a single library."""
    party = _media("Party Mix", 500, "playlist")
    other = _media("Workout", 501, "playlist")
    server = _server(playlists=[party, other])

    assert fuzzy_search(server, "party mx", "playlist") == [party]
    assert (
        fuzzy_search(server, "party mx", "playlist", _section("movie", [], {}, []))
        == []
    )


def test_fuzzy_search_compares_albums_but_not_episodes_without_type() -> None:
    """Test child titles are only compared when they are cheap to list."""
    calls: list = []
    album = _media("Discovery", 11, "album")
    episode = _media("Hello Ms Cobel", 21, "episode")
    music = _section(
        "artist",
        [],
        {"artist": [_media("Daft Punk", 10, "artist")], "album": [album]},
        calls,
    )
    shows = _section(
        "show",
        [],
        {"show": [_media("Severance", 20, "show")], "episode": [episode]},
        calls,
    )
    server = _server(sections=[music, shows])

    assert fuzzy_search(server, "discovry") == [album]
    assert {"libtype": "episode"} not in calls

    # An explicit media type lists the episodes
    assert fuzzy_search(server, "hello ms cobl", "episode") == [episode]


def test_fuzzy_search_ranks_library_results_and_falls_back() -> None:
    """Test results of a library search are ranked and weak ones trigger the fallback."""
    partial = _media("Carrie Goes Home", 1, "movie")
    exact = _media("Carrie", 2, "movie")
    movies = _section("movie", [partial, exact], {}, [])
    server = _server(sections=[movies])

    assert fuzzy_search(server, "carrie", None, movies) == [exact, partial]

    weak = _media("Zzzzzz", 3, "movie")
    wanted = _media("Carrie", 2, "movie")
    movies = _section("movie", [weak], {"movie": [weak, wanted]}, [])
    server = _server(sections=[movies])

    assert fuzzy_search(server, "cary", None, movies) == [wanted, weak]


def test_title_score_tells_numbers_apart() -> None:
    """Test sequels are not mixed up, even when their titles sound alike."""
    query = normalize_title("rocky 3")
    assert title_score(query, "Rocky 3") > title_score(query, "Rocky 4")
    assert title_score(query, "Rocky 3") > title_score(query, "Rocky 2")
