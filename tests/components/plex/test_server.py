"""Tests for Plex server."""
import copy
from unittest.mock import patch

from plexapi.exceptions import BadRequest, NotFound
from requests.exceptions import ConnectionError, RequestException

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    MEDIA_TYPE_EPISODE,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    MEDIA_TYPE_VIDEO,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.plex.const import (
    CONF_IGNORE_NEW_SHARED_USERS,
    CONF_IGNORE_PLEX_WEB_CLIENTS,
    CONF_MONITORED_USERS,
    CONF_SERVER,
    DOMAIN,
    SERVERS,
)
from homeassistant.const import ATTR_ENTITY_ID

from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .helpers import trigger_plex_update, wait_for_debouncer
from .mock_classes import (
    MockPlexAccount,
    MockPlexAlbum,
    MockPlexArtist,
    MockPlexLibrary,
    MockPlexLibrarySection,
    MockPlexMediaItem,
    MockPlexSeason,
    MockPlexServer,
    MockPlexShow,
)


async def test_new_users_available(hass, entry, mock_websocket, setup_plex_server):
    """Test setting up when new users available on Plex server."""
    MONITORED_USERS = {"Owner": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_MONITORED_USERS] = MONITORED_USERS
    entry.options = OPTIONS_WITH_USERS

    mock_plex_server = await setup_plex_server(config_entry=entry)

    server_id = mock_plex_server.machineIdentifier

    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    ignored_users = [x for x in monitored_users if not monitored_users[x]["enabled"]]
    assert len(monitored_users) == 1
    assert len(ignored_users) == 0

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))


async def test_new_ignored_users_available(
    hass, caplog, entry, mock_websocket, setup_plex_server
):
    """Test setting up when new users available on Plex server but are ignored."""
    MONITORED_USERS = {"Owner": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_MONITORED_USERS] = MONITORED_USERS
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_IGNORE_NEW_SHARED_USERS] = True
    entry.options = OPTIONS_WITH_USERS

    mock_plex_server = await setup_plex_server(config_entry=entry)

    server_id = mock_plex_server.machineIdentifier

    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    ignored_users = [x for x in mock_plex_server.accounts if x not in monitored_users]
    assert len(monitored_users) == 1
    assert len(ignored_users) == 2
    for ignored_user in ignored_users:
        ignored_client = [
            x.players[0]
            for x in mock_plex_server.sessions()
            if x.usernames[0] == ignored_user
        ][0]
        assert (
            f"Ignoring {ignored_client.product} client owned by '{ignored_user}'"
            in caplog.text
        )

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))


async def test_network_error_during_refresh(
    hass, caplog, mock_plex_server, mock_websocket
):
    """Test network failures during refreshes."""
    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    with patch.object(mock_plex_server, "clients", side_effect=RequestException):
        await loaded_server._async_update_platforms()
        await hass.async_block_till_done()

    assert (
        f"Could not connect to Plex server: {DEFAULT_DATA[CONF_SERVER]}" in caplog.text
    )


async def test_gdm_client_failure(hass, mock_websocket, setup_plex_server):
    """Test connection failure to a GDM discovered client."""
    with patch(
        "homeassistant.components.plex.server.PlexClient", side_effect=ConnectionError
    ):
        mock_plex_server = await setup_plex_server(disable_gdm=False)
        await hass.async_block_till_done()

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    with patch.object(mock_plex_server, "clients", side_effect=RequestException):
        trigger_plex_update(mock_websocket)
        await hass.async_block_till_done()


async def test_mark_sessions_idle(hass, mock_plex_server, mock_websocket):
    """Test marking media_players as idle when sessions end."""
    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    mock_plex_server.clear_clients()
    mock_plex_server.clear_sessions()

    trigger_plex_update(mock_websocket)
    await hass.async_block_till_done()
    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == "0"


async def test_ignore_plex_web_client(hass, entry, mock_websocket, setup_plex_server):
    """Test option to ignore Plex Web clients."""
    OPTIONS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS[MP_DOMAIN][CONF_IGNORE_PLEX_WEB_CLIENTS] = True
    entry.options = OPTIONS

    with patch("plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(players=0)):
        mock_plex_server = await setup_plex_server(config_entry=entry)
        await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    media_players = hass.states.async_entity_ids("media_player")

    assert len(media_players) == int(sensor.state) - 1


async def test_media_lookups(hass, mock_plex_server, mock_websocket):
    """Test media lookups to Plex server."""
    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    # Plex Key searches
    media_player_id = hass.states.async_entity_ids("media_player")[0]
    with patch("homeassistant.components.plex.PlexServer.create_playqueue"):
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: DOMAIN,
                ATTR_MEDIA_CONTENT_ID: 123,
            },
            True,
        )
    with patch.object(MockPlexServer, "fetchItem", side_effect=NotFound):
        assert await hass.services.async_call(
            MP_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: media_player_id,
                ATTR_MEDIA_CONTENT_TYPE: DOMAIN,
                ATTR_MEDIA_CONTENT_ID: 123,
            },
            True,
        )

    # TV show searches
    with patch.object(MockPlexLibrary, "section", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_EPISODE, library_name="Not a Library", show_name="TV Show"
            )
            is None
        )
    with patch.object(MockPlexLibrarySection, "get", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_EPISODE, library_name="TV Shows", show_name="Not a TV Show"
            )
            is None
        )
    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_EPISODE, library_name="TV Shows", episode_name="An Episode"
        )
        is None
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_EPISODE, library_name="TV Shows", show_name="TV Show"
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_EPISODE,
        library_name="TV Shows",
        show_name="TV Show",
        season_number=2,
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_EPISODE,
        library_name="TV Shows",
        show_name="TV Show",
        season_number=2,
        episode_number=3,
    )
    with patch.object(MockPlexShow, "season", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_EPISODE,
                library_name="TV Shows",
                show_name="TV Show",
                season_number=2,
            )
            is None
        )
    with patch.object(MockPlexSeason, "episode", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_EPISODE,
                library_name="TV Shows",
                show_name="TV Show",
                season_number=2,
                episode_number=1,
            )
            is None
        )

    # Music searches
    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_MUSIC, library_name="Music", album_name="Album"
        )
        is None
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC, library_name="Music", artist_name="Artist"
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC,
        library_name="Music",
        artist_name="Artist",
        track_name="Track 3",
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC,
        library_name="Music",
        artist_name="Artist",
        album_name="Album",
    )
    with patch.object(MockPlexLibrarySection, "get", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MUSIC,
                library_name="Music",
                artist_name="Not an Artist",
                album_name="Album",
            )
            is None
        )
    with patch.object(MockPlexArtist, "album", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MUSIC,
                library_name="Music",
                artist_name="Artist",
                album_name="Not an Album",
            )
            is None
        )
    with patch.object(MockPlexAlbum, "track", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MUSIC,
                library_name="Music",
                artist_name="Artist",
                album_name=" Album",
                track_name="Not a Track",
            )
            is None
        )
    with patch.object(MockPlexArtist, "get", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MUSIC,
                library_name="Music",
                artist_name="Artist",
                track_name="Not a Track",
            )
            is None
        )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC,
        library_name="Music",
        artist_name="Artist",
        album_name="Album",
        track_number=3,
    )
    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_MUSIC,
            library_name="Music",
            artist_name="Artist",
            album_name="Album",
            track_number=30,
        )
        is None
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC,
        library_name="Music",
        artist_name="Artist",
        album_name="Album",
        track_name="Track 3",
    )

    # Playlist searches
    assert loaded_server.lookup_media(MEDIA_TYPE_PLAYLIST, playlist_name="A Playlist")
    assert loaded_server.lookup_media(MEDIA_TYPE_PLAYLIST) is None
    with patch.object(MockPlexServer, "playlist", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_PLAYLIST, playlist_name="Not a Playlist"
            )
            is None
        )

    # Legacy Movie searches
    assert loaded_server.lookup_media(MEDIA_TYPE_VIDEO, video_name="Movie") is None
    assert loaded_server.lookup_media(MEDIA_TYPE_VIDEO, library_name="Movies") is None
    assert loaded_server.lookup_media(
        MEDIA_TYPE_VIDEO, library_name="Movies", video_name="Movie"
    )
    with patch.object(MockPlexLibrarySection, "get", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_VIDEO, library_name="Movies", video_name="Not a Movie"
            )
            is None
        )

    # Movie searches
    assert loaded_server.lookup_media(MEDIA_TYPE_MOVIE, title="Movie") is None
    assert loaded_server.lookup_media(MEDIA_TYPE_MOVIE, library_name="Movies") is None
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MOVIE, library_name="Movies", title="Movie"
    )
    with patch.object(MockPlexLibrarySection, "search", side_effect=BadRequest):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MOVIE, library_name="Movies", title="Not a Movie"
            )
            is None
        )
    with patch.object(MockPlexLibrarySection, "search", return_value=[]):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MOVIE, library_name="Movies", title="Not a Movie"
            )
            is None
        )

    similar_movies = []
    for title in "Duplicate Movie", "Duplicate Movie 2":
        similar_movies.append(MockPlexMediaItem(title))
    with patch.object(
        loaded_server.library.section("Movies"), "search", return_value=similar_movies
    ):
        found_media = loaded_server.lookup_media(
            MEDIA_TYPE_MOVIE, library_name="Movies", title="Duplicate Movie"
        )
    assert found_media.title == "Duplicate Movie"

    duplicate_movies = []
    for title in "Duplicate Movie - Original", "Duplicate Movie - Remake":
        duplicate_movies.append(MockPlexMediaItem(title))
    with patch.object(
        loaded_server.library.section("Movies"), "search", return_value=duplicate_movies
    ):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MOVIE, library_name="Movies", title="Duplicate Movie"
            )
        ) is None
