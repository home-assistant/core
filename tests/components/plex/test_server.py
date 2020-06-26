"""Tests for Plex server."""
import copy

from plexapi.exceptions import NotFound
from requests.exceptions import RequestException

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    MEDIA_TYPE_EPISODE,
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
from .helpers import trigger_plex_update
from .mock_classes import (
    MockPlexAccount,
    MockPlexArtist,
    MockPlexLibrary,
    MockPlexLibrarySection,
    MockPlexMediaItem,
    MockPlexServer,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_new_users_available(hass):
    """Test setting up when new users available on Plex server."""

    MONITORED_USERS = {"Owner": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_MONITORED_USERS] = MONITORED_USERS

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=OPTIONS_WITH_USERS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket.listen"):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier

    trigger_plex_update(hass, mock_plex_server)
    await hass.async_block_till_done()

    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    ignored_users = [x for x in monitored_users if not monitored_users[x]["enabled"]]
    assert len(monitored_users) == 1
    assert len(ignored_users) == 0

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))


async def test_new_ignored_users_available(hass, caplog):
    """Test setting up when new users available on Plex server but are ignored."""

    MONITORED_USERS = {"Owner": {"enabled": True}}
    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_MONITORED_USERS] = MONITORED_USERS
    OPTIONS_WITH_USERS[MP_DOMAIN][CONF_IGNORE_NEW_SHARED_USERS] = True

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=OPTIONS_WITH_USERS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket.listen"):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier

    trigger_plex_update(hass, mock_plex_server)
    await hass.async_block_till_done()

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

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))


async def test_network_error_during_refresh(hass, caplog):
    """Test network failures during refreshes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer()

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket.listen"):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    trigger_plex_update(hass, mock_plex_server)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    with patch.object(mock_plex_server, "clients", side_effect=RequestException):
        await loaded_server._async_update_platforms()
        await hass.async_block_till_done()

    assert (
        f"Could not connect to Plex server: {DEFAULT_DATA[CONF_SERVER]}" in caplog.text
    )


async def test_mark_sessions_idle(hass):
    """Test marking media_players as idle when sessions end."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer()

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket.listen"):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    trigger_plex_update(hass, mock_plex_server)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    mock_plex_server.clear_clients()
    mock_plex_server.clear_sessions()

    await loaded_server._async_update_platforms()
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == "0"


async def test_ignore_plex_web_client(hass):
    """Test option to ignore Plex Web clients."""

    OPTIONS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS[MP_DOMAIN][CONF_IGNORE_PLEX_WEB_CLIENTS] = True

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(players=0)
    ), patch("homeassistant.components.plex.PlexWebsocket.listen"):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    trigger_plex_update(hass, mock_plex_server)
    await hass.async_block_till_done()

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    media_players = hass.states.async_entity_ids("media_player")

    assert len(media_players) == int(sensor.state) - 1


async def test_media_lookups(hass):
    """Test media lookups to Plex server."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket.listen"):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[DOMAIN][SERVERS][server_id]

    # Plex Key searches
    trigger_plex_update(hass, mock_plex_server)
    await hass.async_block_till_done()

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
                MEDIA_TYPE_EPISODE, library_name="Not a Library", show_name="A TV Show"
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
        MEDIA_TYPE_EPISODE, library_name="TV Shows", show_name="A TV Show"
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_EPISODE,
        library_name="TV Shows",
        show_name="A TV Show",
        season_number=2,
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_EPISODE,
        library_name="TV Shows",
        show_name="A TV Show",
        season_number=2,
        episode_number=3,
    )
    with patch.object(MockPlexMediaItem, "season", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_EPISODE,
                library_name="TV Shows",
                show_name="A TV Show",
                season_number=2,
            )
            is None
        )
    with patch.object(MockPlexMediaItem, "episode", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_EPISODE,
                library_name="TV Shows",
                show_name="A TV Show",
                season_number=2,
                episode_number=1,
            )
            is None
        )

    # Music searches
    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_MUSIC, library_name="Music", album_name="An Album"
        )
        is None
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC, library_name="Music", artist_name="An Artist"
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC,
        library_name="Music",
        artist_name="An Artist",
        track_name="A Track",
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC,
        library_name="Music",
        artist_name="An Artist",
        album_name="An Album",
    )
    with patch.object(MockPlexLibrarySection, "get", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MUSIC,
                library_name="Music",
                artist_name="Not an Artist",
                album_name="An Album",
            )
            is None
        )
    with patch.object(MockPlexArtist, "album", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MUSIC,
                library_name="Music",
                artist_name="An Artist",
                album_name="Not an Album",
            )
            is None
        )
    with patch.object(MockPlexMediaItem, "track", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MUSIC,
                library_name="Music",
                artist_name="An Artist",
                album_name="An Album",
                track_name="Not a Track",
            )
            is None
        )
    with patch.object(MockPlexArtist, "get", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_MUSIC,
                library_name="Music",
                artist_name="An Artist",
                track_name="Not a Track",
            )
            is None
        )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC,
        library_name="Music",
        artist_name="An Artist",
        album_name="An Album",
        track_number=3,
    )
    assert (
        loaded_server.lookup_media(
            MEDIA_TYPE_MUSIC,
            library_name="Music",
            artist_name="An Artist",
            album_name="An Album",
            track_number=30,
        )
        is None
    )
    assert loaded_server.lookup_media(
        MEDIA_TYPE_MUSIC,
        library_name="Music",
        artist_name="An Artist",
        album_name="An Album",
        track_name="A Track",
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

    # Movie searches
    assert loaded_server.lookup_media(MEDIA_TYPE_VIDEO, video_name="A Movie") is None
    assert loaded_server.lookup_media(MEDIA_TYPE_VIDEO, library_name="Movies") is None
    assert loaded_server.lookup_media(
        MEDIA_TYPE_VIDEO, library_name="Movies", video_name="A Movie"
    )
    with patch.object(MockPlexLibrarySection, "get", side_effect=NotFound):
        assert (
            loaded_server.lookup_media(
                MEDIA_TYPE_VIDEO, library_name="Movies", video_name="Not a Movie"
            )
            is None
        )
