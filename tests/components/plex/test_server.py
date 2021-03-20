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


async def test_new_users_available(hass, entry, setup_plex_server):
    """Test setting up when new users available on Plex server."""
    MONITORED_USERS = {"User 1": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_MONITORED_USERS] = MONITORED_USERS
    entry.options = OPTIONS_WITH_USERS

    mock_plex_server = await setup_plex_server(config_entry=entry)

    server_id = mock_plex_server.machine_identifier

    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    ignored_users = [x for x in monitored_users if not monitored_users[x]["enabled"]]
    assert len(monitored_users) == 1
    assert len(ignored_users) == 0


async def test_new_ignored_users_available(
    hass,
    caplog,
    entry,
    mock_websocket,
    setup_plex_server,
    requests_mock,
    session_new_user,
):
    """Test setting up when new users available on Plex server but are ignored."""
    MONITORED_USERS = {"User 1": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_MONITORED_USERS] = MONITORED_USERS
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_IGNORE_NEW_SHARED_USERS] = True
    entry.options = OPTIONS_WITH_USERS

    mock_plex_server = await setup_plex_server(config_entry=entry)

    requests_mock.get(
        f"{mock_plex_server.url_in_use}/status/sessions",
        text=session_new_user,
    )
    trigger_plex_update(mock_websocket)
    await wait_for_debouncer(hass)

    server_id = mock_plex_server.machine_identifier

    active_sessions = mock_plex_server._plex_server.sessions()
    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users
    ignored_users = [x for x in mock_plex_server.accounts if x not in monitored_users]

    assert len(monitored_users) == 1
    assert len(ignored_users) == 2

    for ignored_user in ignored_users:
        ignored_client = [
            x.players[0] for x in active_sessions if x.usernames[0] == ignored_user
        ]
        if ignored_client:
            assert (
                f"Ignoring {ignored_client[0].product} client owned by '{ignored_user}'"
                in caplog.text
            )

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))


async def test_network_error_during_refresh(hass, caplog, mock_plex_server):
    """Test network failures during refreshes."""
    server_id = mock_plex_server.machine_identifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]
    active_sessions = mock_plex_server._plex_server.sessions()

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))

    with patch("plexapi.server.PlexServer.clients", side_effect=RequestException):
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

    active_sessions = mock_plex_server._plex_server.sessions()
    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))

    with patch("plexapi.server.PlexServer.clients", side_effect=RequestException):
        trigger_plex_update(mock_websocket)
        await hass.async_block_till_done()


async def test_mark_sessions_idle(
    hass, mock_plex_server, mock_websocket, requests_mock, empty_payload
):
    """Test marking media_players as idle when sessions end."""
    await wait_for_debouncer(hass)

    active_sessions = mock_plex_server._plex_server.sessions()

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))

    url = mock_plex_server.url_in_use
    requests_mock.get(f"{url}/clients", text=empty_payload)
    requests_mock.get(f"{url}/status/sessions", text=empty_payload)

    trigger_plex_update(mock_websocket)
    await hass.async_block_till_done()
    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == "0"


async def test_ignore_plex_web_client(hass, entry, setup_plex_server):
    """Test option to ignore Plex Web clients."""
    OPTIONS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS[MP_DOMAIN][CONF_IGNORE_PLEX_WEB_CLIENTS] = True
    entry.options = OPTIONS

    mock_plex_server = await setup_plex_server(
        config_entry=entry, client_type="plexweb", disable_clients=True
    )
    await wait_for_debouncer(hass)

    active_sessions = mock_plex_server._plex_server.sessions()
    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(active_sessions))

    media_players = hass.states.async_entity_ids("media_player")

    assert len(media_players) == int(sensor.state) - 1


async def test_media_lookups(hass, mock_plex_server, requests_mock, playqueue_created):
    """Test media lookups to Plex server."""
    server_id = mock_plex_server.machine_identifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    # Plex Key searches
    media_player_id = hass.states.async_entity_ids("media_player")[0]
    requests_mock.post("/playqueues", text=playqueue_created)
    requests_mock.get("/player/playback/playMedia", status_code=200)
    assert await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: media_player_id,
            ATTR_MEDIA_CONTENT_TYPE: DOMAIN,
            ATTR_MEDIA_CONTENT_ID: 1,
        },
        True,
    )
    with patch("plexapi.server.PlexServer.fetchItem", side_effect=NotFound):
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
    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_EPISODE, library_name="Not a Library", show_name="TV Show"
        )
        is None
    )
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
        season_number=1,
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_EPISODE,
        library_name="TV Shows",
        show_name="TV Show",
        season_number=1,
        episode_number=3,
    )
    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_EPISODE,
            library_name="TV Shows",
            show_name="TV Show",
            season_number=2,
        )
        is None
    )
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
    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_MUSIC,
            library_name="Music",
            artist_name="Not an Artist",
            album_name="Album",
        )
        is None
    )
    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_MUSIC,
            library_name="Music",
            artist_name="Artist",
            album_name="Not an Album",
        )
        is None
    )
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
    assert loaded_server.lookup_media(MEDIA_TYPE_PLAYLIST, playlist_name="Playlist 1")
    assert loaded_server.lookup_media(MEDIA_TYPE_PLAYLIST) is None
    assert (
        loaded_server.lookup_media(MEDIA_TYPE_PLAYLIST, playlist_name="Not a Playlist")
        is None
    )

    # Legacy Movie searches
    assert loaded_server.lookup_media(MEDIA_TYPE_VIDEO, video_name="Movie") is None
    assert loaded_server.lookup_media(MEDIA_TYPE_VIDEO, library_name="Movies") is None
    assert loaded_server.lookup_media(
        MEDIA_TYPE_VIDEO, library_name="Movies", video_name="Movie 1"
    )
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
        MEDIA_TYPE_MOVIE, library_name="Movies", title="Movie 1"
    )
    with patch("plexapi.library.LibrarySection.search", side_effect=BadRequest):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MOVIE, library_name="Movies", title="Not a Movie"
            )
            is None
        )

    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_MOVIE, library_name="Movies", title="Movie"
        )
    ) is None
