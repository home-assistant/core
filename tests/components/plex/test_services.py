"""Tests for various Plex services."""

from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch

import plexapi.audio
from plexapi.exceptions import NotFound
import plexapi.playqueue
import plexapi.video
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests_mock

from homeassistant.components.media_player import MediaType
from homeassistant.components.plex.const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DOMAIN,
    PLEX_SERVER_CONFIG,
    PLEX_URI_SCHEME,
    SERVICE_ON_DECK,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SEARCH,
)
from homeassistant.components.plex.services import (
    _media_result_info,
    process_plex_payload,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DEFAULT_DATA, DEFAULT_OPTIONS, SECONDARY_DATA


async def test_refresh_library(
    hass: HomeAssistant,
    mock_plex_server,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    empty_payload,
    plex_server_accounts,
    plex_server_base,
) -> None:
    """Test refresh_library service call."""
    url = mock_plex_server.url_in_use
    refresh = requests_mock.get(
        f"{url}/library/sections/1/refresh", status_code=HTTPStatus.OK
    )

    # Test with non-existent server
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"server_name": "Not a Server", "library_name": "Movies"},
            True,
        )
    assert not refresh.called

    # Test with non-existent library
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        {"library_name": "Not a Library"},
        True,
    )
    assert not refresh.called

    # Test with valid library
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        {"library_name": "Movies"},
        True,
    )
    assert refresh.call_count == 1

    # Add a second configured server
    secondary_url = SECONDARY_DATA[PLEX_SERVER_CONFIG][CONF_URL]
    secondary_name = SECONDARY_DATA[CONF_SERVER]
    secondary_id = SECONDARY_DATA[CONF_SERVER_IDENTIFIER]
    requests_mock.get(
        secondary_url,
        text=plex_server_base.format(
            name=secondary_name, machine_identifier=secondary_id
        ),
    )
    requests_mock.get(f"{secondary_url}/accounts", text=plex_server_accounts)
    requests_mock.get(f"{secondary_url}/clients", text=empty_payload)
    requests_mock.get(f"{secondary_url}/status/sessions", text=empty_payload)

    entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data=SECONDARY_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=SECONDARY_DATA["server_id"],
    )

    await setup_plex_server(config_entry=entry_2)

    # Test multiple servers available but none specified
    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"library_name": "Movies"},
            True,
        )
    assert "Multiple Plex servers configured" in str(excinfo.value)
    assert refresh.call_count == 1


async def test_search_service(
    hass: HomeAssistant,
    mock_plex_server,
    requests_mock: requests_mock.Mocker,
    hubs_search,
    playlists,
) -> None:
    """Test search service call."""
    url = mock_plex_server.url_in_use
    requests_mock.get(f"{url}/playlists/500", text=playlists)
    requests_mock.get(f"{url}/hubs/search", text=hubs_search)

    # Test server-wide search across media types
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {"query": "Movie 1"},
        blocking=True,
        return_response=True,
    )
    assert len(result["results"]) == 2

    movie_result = next(x for x in result["results"] if x["media_type"] == "movie")
    assert movie_result["title"] == "Movie 1"
    assert movie_result["year"] == 2000
    assert movie_result["summary"] == "Some elaborate summary."
    assert movie_result["guid"] == "plex://movie/5d776b85594b2b001e6dc641"
    assert movie_result["rating_key"] == 1
    assert movie_result["key"] == "/library/metadata/1"
    assert movie_result["thumb_path"] == (
        f"/api/plex_image_proxy/{mock_plex_server.machine_identifier}/1"
    )
    assert movie_result["thumb_url"].startswith(
        f"{movie_result['thumb_path']}?authSig="
    )
    assert "X-Plex-Token" not in movie_result["thumb_url"]
    assert movie_result["server_id"] == mock_plex_server.machine_identifier
    assert movie_result["server_name"] == mock_plex_server.friendly_name
    assert movie_result["library_name"] == "Movies"
    assert movie_result["content_rating"] == "R"
    assert movie_result["duration"] == 9000000
    assert movie_result["originally_available_at"].startswith("2000-01-01")
    assert movie_result["genres"] == ["Sci-Fi", "Action"]

    show_result = next(x for x in result["results"] if x["media_type"] == "show")
    assert show_result["title"] == "TV Show"
    assert "on_deck" not in show_result
    assert "on_deck" not in movie_result
    assert show_result["guid"] == "plex://show/5d9c07f7e98e47001eb03fc7"

    # Test the on deck episode is included for shows
    on_deck_episode = SimpleNamespace(
        title="Episode 5",
        type="episode",
        guid="plex://episode/60d5ff1c4a0721002c4e5d75",
        ratingKey=35,
        key="/library/metadata/35",
    )
    with patch.object(plexapi.video.Show, "onDeck", return_value=on_deck_episode):
        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {"query": "TV Show", "media_type": "show", "include_on_deck": True},
            blocking=True,
            return_response=True,
        )
    assert result["results"][0]["on_deck"]["title"] == "Episode 5"
    assert result["results"][0]["on_deck"]["rating_key"] == 35

    # Test search scoped to a specific media type
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {"query": "Movie 1", "media_type": "movie"},
        blocking=True,
        return_response=True,
    )
    assert len(result["results"]) == 1
    assert result["results"][0]["media_type"] == "movie"

    # Test search scoped to a specific library
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {"query": "Movie 1", "library_name": "Movies"},
        blocking=True,
        return_response=True,
    )
    assert len(result["results"]) == 5
    assert all(x["media_type"] == "movie" for x in result["results"])

    # Test with non-existent library
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {"query": "Movie 1", "library_name": "Not a Library"},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "library_not_found"
    assert exc_info.value.translation_placeholders["library"] == "Not a Library"
    assert "Movies" in exc_info.value.translation_placeholders["libraries"]

    # Test with non-existent server
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {"query": "Movie 1", "server_name": "Not a Server"},
            blocking=True,
            return_response=True,
        )

    # Test lookup by Plex key
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {"plex_key": 1},
        blocking=True,
        return_response=True,
    )
    assert [x["title"] for x in result["results"]] == ["Movie 1"]

    # Test lookup of an unknown Plex key
    requests_mock.get(f"{url}/library/metadata/999", status_code=HTTPStatus.NOT_FOUND)
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {"plex_key": 999},
        blocking=True,
        return_response=True,
    )
    assert result["results"] == []

    # Test playlist lookup
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {"playlist_name": "Playlist 1"},
        blocking=True,
        return_response=True,
    )
    assert [x["title"] for x in result["results"]] == ["Playlist 1"]
    assert result["results"][0]["media_type"] == "playlist"

    # Test play_media compatible filters in a library
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {"library_name": "TV Shows", "show_name": "TV Show", "media_type": "show"},
        blocking=True,
        return_response=True,
    )
    assert len(result["results"]) == 1
    assert result["results"][0]["media_type"] == "show"

    # Test filters without a library
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {"year": 2000},
            blocking=True,
            return_response=True,
        )
    assert exc_info.value.translation_key == "library_required"

    # Test a call without any search criteria
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {"library_name": "Movies"},
            blocking=True,
            return_response=True,
        )


async def test_lookup_media_for_other_integrations(
    hass: HomeAssistant,
    entry,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
    playqueue_1234,
    playqueue_created,
) -> None:
    """Test media lookup for media_player.play_media calls from cast/sonos."""
    CONTENT_ID = PLEX_URI_SCHEME + '{"library_name": "Music", "artist_name": "Artist"}'
    CONTENT_ID_KEY = PLEX_URI_SCHEME + "100"
    CONTENT_ID_BAD_MEDIA = (
        PLEX_URI_SCHEME + '{"library_name": "Music", "artist_name": "Not an Artist"}'
    )
    CONTENT_ID_PLAYQUEUE = PLEX_URI_SCHEME + '{"playqueue_id": 1234}'
    CONTENT_ID_BAD_PLAYQUEUE = PLEX_URI_SCHEME + '{"playqueue_id": 1235}'
    CONTENT_ID_SERVER = (
        PLEX_URI_SCHEME + '{"plex_server": "Plex Server 1",'
        ' "library_name": "Music", "artist_name": "Artist"}'
    )
    CONTENT_ID_SHUFFLE = (
        PLEX_URI_SCHEME
        + '{"library_name": "Music", "artist_name": "Artist", "shuffle": 1}'
    )
    CONTENT_ID_CONTINUOUS = (
        PLEX_URI_SCHEME
        + '{"library_name": "Music", "artist_name": "Artist", "continuous": 1}'
    )

    # Test with no Plex integration available
    with pytest.raises(HomeAssistantError) as excinfo:
        process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID)
    assert "Plex integration not configured" in str(excinfo.value)

    with patch(
        "homeassistant.components.plex.PlexServer.connect", side_effect=NotFound
    ):
        # Initialize Plex integration without setting up a server
        with pytest.raises(AssertionError):
            await setup_plex_server()

        # Test with no Plex servers available
        with pytest.raises(HomeAssistantError) as excinfo:
            process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID)
        assert "No Plex servers available" in str(excinfo.value)

    # Complete setup of a Plex server
    await hass.config_entries.async_unload(entry.entry_id)
    await setup_plex_server()

    # Test lookup success without playqueue
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Artist)
    assert not result.shuffle
    assert not result.continuous

    # Test media key payload without playqueue
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_KEY, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Track)
    assert not result.shuffle

    # Test with specified server without playqueue
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_SERVER, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Artist)
    assert not result.shuffle

    # Test shuffle without playqueue
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_SHUFFLE, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Artist)
    assert result.shuffle

    # Test continuous without playqueue
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_CONTINUOUS, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Artist)
    assert result.continuous

    # Test with media not found
    with patch(
        "plexapi.library.LibrarySection.search",
        return_value=None,
        __qualname__="search",
    ):
        with pytest.raises(HomeAssistantError) as excinfo:
            process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID_BAD_MEDIA)
        assert f"No {MediaType.MUSIC} results in 'Music' for" in str(excinfo.value)

    # Test with playqueue
    requests_mock.get("https://1.2.3.4:32400/playQueues/1234", text=playqueue_1234)
    result = process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID_PLAYQUEUE)
    assert isinstance(result.media, plexapi.playqueue.PlayQueue)

    # Test with invalid playqueue
    requests_mock.get(
        "https://1.2.3.4:32400/playQueues/1235", status_code=HTTPStatus.NOT_FOUND
    )
    with pytest.raises(HomeAssistantError) as excinfo:
        process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID_BAD_PLAYQUEUE)
    assert "PlayQueue '1235' could not be found" in str(excinfo.value)

    # Test playqueue is created with shuffle
    requests_mock.post("/playqueues", text=playqueue_created)
    result = process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID_SHUFFLE)
    assert isinstance(result.media, plexapi.playqueue.PlayQueue)

    # Test playqueue is created with continuous
    result = process_plex_payload(hass, MediaType.MUSIC, CONTENT_ID_CONTINUOUS)
    assert isinstance(result.media, plexapi.playqueue.PlayQueue)


async def test_lookup_media_with_urls(hass: HomeAssistant, mock_plex_server) -> None:
    """Test media lookup for media_player.play_media calls from cast/sonos."""
    CONTENT_ID_URL = f"{PLEX_URI_SCHEME}{DEFAULT_DATA[CONF_SERVER_IDENTIFIER]}/100"

    # Test URL format
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_URL, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Track)
    assert result.shuffle is False

    # Test URL format with shuffle
    CONTENT_ID_URL_WITH_SHUFFLE = CONTENT_ID_URL + "?shuffle=1"
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_URL_WITH_SHUFFLE, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Track)
    assert result.shuffle is True
    assert result.offset == 0

    # Test URL format with continuous
    CONTENT_ID_URL_WITH_CONTINUOUS = CONTENT_ID_URL + "?continuous=1"
    result = process_plex_payload(
        hass, MediaType.MUSIC, CONTENT_ID_URL_WITH_CONTINUOUS, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.audio.Track)
    assert result.continuous is True
    assert result.offset == 0


async def test_on_deck_service(
    hass: HomeAssistant,
    mock_plex_server,
    requests_mock: requests_mock.Mocker,
    library_movies_all,
) -> None:
    """Test the on deck service."""
    url = mock_plex_server.url_in_use
    requests_mock.get(f"{url}/hubs/continueWatching/items", text=library_movies_all)

    result = await hass.services.async_call(
        DOMAIN, SERVICE_ON_DECK, {}, blocking=True, return_response=True
    )
    assert len(result["results"]) == 5
    first = result["results"][0]
    assert first["title"] == "Movie 1"
    assert first["media_type"] == "movie"
    assert first["server_id"] == mock_plex_server.machine_identifier
    assert first["progress_percent"] is None

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_ON_DECK,
        {"limit": 2, "library_name": "Movies", "media_type": "movie"},
        blocking=True,
        return_response=True,
    )
    assert len(result["results"]) == 2

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_ON_DECK,
        {"media_type": "episode"},
        blocking=True,
        return_response=True,
    )
    assert result["results"] == []

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_ON_DECK,
        {"library_name": "TV Shows"},
        blocking=True,
        return_response=True,
    )
    assert result["results"] == []


async def test_search_service_library_filters(
    hass: HomeAssistant, mock_plex_server
) -> None:
    """Test a library search with a field filter and a media type."""
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH,
        {"library_name": "Movies", "year": 2000, "media_type": "movie"},
        blocking=True,
        return_response=True,
    )
    assert len(result["results"]) == 5


async def test_search_service_advanced_filters(
    hass: HomeAssistant, mock_plex_server
) -> None:
    """Test an advanced filter expression reaches Plex unchanged."""
    expression = {"or": [{"genre": "Action"}, {"genre": "Comedy"}]}
    with patch(
        "plexapi.library.LibrarySection.search",
        return_value=[],
        __qualname__="search",
    ) as search:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {
                "library_name": "Movies",
                "year": 2000,
                "media_type": "movie",
                "filters": expression,
            },
            blocking=True,
            return_response=True,
        )

    assert search.call_args.kwargs["filters"] == expression
    assert "or" not in search.call_args.kwargs
    assert search.call_args.kwargs["year"] == 2000
    assert search.call_args.kwargs["libtype"] == "movie"


async def test_media_result_info_hierarchy(mock_plex_server) -> None:
    """Test the parent fields describe the right objects for each media type."""
    season = SimpleNamespace(
        title="Season 2",
        type="season",
        guid="plex://season/1",
        ratingKey=21,
        key="/library/metadata/21",
        parentTitle="TV Show",
        parentRatingKey=20,
        parentGuid="plex://show/1",
        index=2,
    )
    info = _media_result_info(season, mock_plex_server)
    assert info["show_title"] == "TV Show"
    assert info["show_rating_key"] == 20
    assert info["show_guid"] == "plex://show/1"
    assert info["season_number"] == 2
    assert "season_title" not in info

    track = SimpleNamespace(
        title="Track 3",
        type="track",
        guid="plex://track/1",
        ratingKey=33,
        key="/library/metadata/33",
        parentTitle="Album",
        grandparentTitle="Artist",
        index=3,
    )
    info = _media_result_info(track, mock_plex_server)
    assert info["artist_name"] == "Artist"
    assert info["album_title"] == "Album"
    assert info["track_number"] == 3
    assert "show_title" not in info
    assert info["thumb_path"] is None
    assert info["thumb_url"] is None


async def test_play_show_resumes_on_deck_episode(
    hass: HomeAssistant, mock_plex_server
) -> None:
    """Test a show resolves to its on deck episode only when resume is set."""
    content_id = f"{PLEX_URI_SCHEME}{DEFAULT_DATA[CONF_SERVER_IDENTIFIER]}/30"

    result = process_plex_payload(
        hass, MediaType.TVSHOW, content_id, supports_playqueues=False
    )
    assert isinstance(result.media, plexapi.video.Show)

    on_deck_episode = SimpleNamespace(type="episode")
    with patch.object(plexapi.video.Show, "onDeck", return_value=on_deck_episode):
        result = process_plex_payload(
            hass, MediaType.TVSHOW, f"{content_id}?resume=1", supports_playqueues=False
        )
    assert result.media is on_deck_episode

    with patch.object(plexapi.video.Show, "onDeck", return_value=None):
        result = process_plex_payload(
            hass, MediaType.TVSHOW, f"{content_id}?resume=1", supports_playqueues=False
        )
    assert isinstance(result.media, plexapi.video.Show)
    assert result.offset == 0


async def test_search_service_season_zero(
    hass: HomeAssistant, mock_plex_server
) -> None:
    """Test a season number of zero is kept in the search."""
    with patch(
        "plexapi.library.LibrarySection.search",
        return_value=[],
        __qualname__="search",
    ) as search:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {
                "library_name": "TV Shows",
                "show_name": "TV Show",
                "season_number": 0,
                "media_type": "episode",
            },
            blocking=True,
            return_response=True,
        )

    assert search.call_args.kwargs["season.index"] == 0
    assert search.call_args.kwargs["libtype"] == "episode"


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (SERVICE_SEARCH, {"query": "Movie 1", "username": "unknown"}),
        (SERVICE_ON_DECK, {"username": "unknown"}),
    ],
)
async def test_unknown_username(
    hass: HomeAssistant, mock_plex_server, service: str, data: dict[str, str]
) -> None:
    """Test an unknown Plex user gives a clear error."""
    with (
        patch(
            "homeassistant.components.plex.server.PlexServer.switch_user",
            side_effect=NotFound,
        ),
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN, service, data, blocking=True, return_response=True
        )

    assert exc_info.value.translation_key == "user_not_found"
    assert exc_info.value.translation_placeholders == {"user": "unknown"}
