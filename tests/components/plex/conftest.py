"""Fixtures for Plex tests."""
from unittest.mock import patch

import pytest

from homeassistant.components.plex.const import DOMAIN, PLEX_SERVER_CONFIG, SERVERS
from homeassistant.const import CONF_URL

from .const import DEFAULT_DATA, DEFAULT_OPTIONS, PLEX_DIRECT_URL
from .helpers import websocket_connected
from .mock_classes import MockGDM

from tests.common import MockConfigEntry, load_fixture


def plex_server_url(entry):
    """Return a protocol-less URL from a config entry."""
    return entry.data[PLEX_SERVER_CONFIG][CONF_URL].split(":", 1)[-1]


@pytest.fixture(name="album", scope="session")
def album_fixture():
    """Load album payload and return it."""
    return load_fixture("plex/album.xml")


@pytest.fixture(name="artist_albums", scope="session")
def artist_albums_fixture():
    """Load artist's albums payload and return it."""
    return load_fixture("plex/artist_albums.xml")


@pytest.fixture(name="children_20", scope="session")
def children_20_fixture():
    """Load children payload for item 20 and return it."""
    return load_fixture("plex/children_20.xml")


@pytest.fixture(name="children_30", scope="session")
def children_30_fixture():
    """Load children payload for item 30 and return it."""
    return load_fixture("plex/children_30.xml")


@pytest.fixture(name="children_200", scope="session")
def children_200_fixture():
    """Load children payload for item 200 and return it."""
    return load_fixture("plex/children_200.xml")


@pytest.fixture(name="children_300", scope="session")
def children_300_fixture():
    """Load children payload for item 300 and return it."""
    return load_fixture("plex/children_300.xml")


@pytest.fixture(name="empty_library", scope="session")
def empty_library_fixture():
    """Load an empty library payload and return it."""
    return load_fixture("plex/empty_library.xml")


@pytest.fixture(name="empty_payload", scope="session")
def empty_payload_fixture():
    """Load an empty payload and return it."""
    return load_fixture("plex/empty_payload.xml")


@pytest.fixture(name="grandchildren_300", scope="session")
def grandchildren_300_fixture():
    """Load grandchildren payload for item 300 and return it."""
    return load_fixture("plex/grandchildren_300.xml")


@pytest.fixture(name="library_movies_all", scope="session")
def library_movies_all_fixture():
    """Load payload for all items in the movies library and return it."""
    return load_fixture("plex/library_movies_all.xml")


@pytest.fixture(name="library_tvshows_all", scope="session")
def library_tvshows_all_fixture():
    """Load payload for all items in the tvshows library and return it."""
    return load_fixture("plex/library_tvshows_all.xml")


@pytest.fixture(name="library_music_all", scope="session")
def library_music_all_fixture():
    """Load payload for all items in the music library and return it."""
    return load_fixture("plex/library_music_all.xml")


@pytest.fixture(name="library_movies_sort", scope="session")
def library_movies_sort_fixture():
    """Load sorting payload for movie library and return it."""
    return load_fixture("plex/library_movies_sort.xml")


@pytest.fixture(name="library_tvshows_sort", scope="session")
def library_tvshows_sort_fixture():
    """Load sorting payload for tvshow library and return it."""
    return load_fixture("plex/library_tvshows_sort.xml")


@pytest.fixture(name="library_music_sort", scope="session")
def library_music_sort_fixture():
    """Load sorting payload for music library and return it."""
    return load_fixture("plex/library_music_sort.xml")


@pytest.fixture(name="library_movies_filtertypes", scope="session")
def library_movies_filtertypes_fixture():
    """Load filtertypes payload for movie library and return it."""
    return load_fixture("plex/library_movies_filtertypes.xml")


@pytest.fixture(name="library", scope="session")
def library_fixture():
    """Load library payload and return it."""
    return load_fixture("plex/library.xml")


@pytest.fixture(name="library_tvshows_size", scope="session")
def library_tvshows_size_fixture():
    """Load tvshow library size payload and return it."""
    return load_fixture("plex/library_tvshows_size.xml")


@pytest.fixture(name="library_tvshows_size_episodes", scope="session")
def library_tvshows_size_episodes_fixture():
    """Load tvshow library size in episodes payload and return it."""
    return load_fixture("plex/library_tvshows_size_episodes.xml")


@pytest.fixture(name="library_tvshows_size_seasons", scope="session")
def library_tvshows_size_seasons_fixture():
    """Load tvshow library size in seasons payload and return it."""
    return load_fixture("plex/library_tvshows_size_seasons.xml")


@pytest.fixture(name="library_sections", scope="session")
def library_sections_fixture():
    """Load library sections payload and return it."""
    return load_fixture("plex/library_sections.xml")


@pytest.fixture(name="media_1", scope="session")
def media_1_fixture():
    """Load media payload for item 1 and return it."""
    return load_fixture("plex/media_1.xml")


@pytest.fixture(name="media_30", scope="session")
def media_30_fixture():
    """Load media payload for item 30 and return it."""
    return load_fixture("plex/media_30.xml")


@pytest.fixture(name="media_100", scope="session")
def media_100_fixture():
    """Load media payload for item 100 and return it."""
    return load_fixture("plex/media_100.xml")


@pytest.fixture(name="media_200", scope="session")
def media_200_fixture():
    """Load media payload for item 200 and return it."""
    return load_fixture("plex/media_200.xml")


@pytest.fixture(name="player_plexweb_resources", scope="session")
def player_plexweb_resources_fixture():
    """Load resources payload for a Plex Web player and return it."""
    return load_fixture("plex/player_plexweb_resources.xml")


@pytest.fixture(name="playlists", scope="session")
def playlists_fixture():
    """Load payload for all playlists and return it."""
    return load_fixture("plex/playlists.xml")


@pytest.fixture(name="playlist_500", scope="session")
def playlist_500_fixture():
    """Load payload for playlist 500 and return it."""
    return load_fixture("plex/playlist_500.xml")


@pytest.fixture(name="playqueue_created", scope="session")
def playqueue_created_fixture():
    """Load payload for playqueue creation response and return it."""
    return load_fixture("plex/playqueue_created.xml")


@pytest.fixture(name="playqueue_1234", scope="session")
def playqueue_1234_fixture():
    """Load payload for playqueue 1234 and return it."""
    return load_fixture("plex/playqueue_1234.xml")


@pytest.fixture(name="plex_server_accounts", scope="session")
def plex_server_accounts_fixture():
    """Load payload accounts on the Plex server and return it."""
    return load_fixture("plex/plex_server_accounts.xml")


@pytest.fixture(name="plex_server_base", scope="session")
def plex_server_base_fixture():
    """Load base payload for Plex server info and return it."""
    return load_fixture("plex/plex_server_base.xml")


@pytest.fixture(name="plex_server_default", scope="session")
def plex_server_default_fixture(plex_server_base):
    """Load default payload for Plex server info and return it."""
    return plex_server_base.format(
        name="Plex Server 1", machine_identifier="unique_id_123"
    )


@pytest.fixture(name="plex_server_clients", scope="session")
def plex_server_clients_fixture():
    """Load available clients payload for Plex server and return it."""
    return load_fixture("plex/plex_server_clients.xml")


@pytest.fixture(name="plextv_account", scope="session")
def plextv_account_fixture():
    """Load account info from plex.tv and return it."""
    return load_fixture("plex/plextv_account.xml")


@pytest.fixture(name="plextv_resources_base", scope="session")
def plextv_resources_base_fixture():
    """Load base payload for plex.tv resources and return it."""
    return load_fixture("plex/plextv_resources_base.xml")


@pytest.fixture(name="plextv_resources", scope="session")
def plextv_resources_fixture(plextv_resources_base):
    """Load default payload for plex.tv resources and return it."""
    return plextv_resources_base.format(second_server_enabled=0)


@pytest.fixture(name="plextv_shared_users", scope="session")
def plextv_shared_users_fixture(plextv_resources_base):
    """Load payload for plex.tv shared users and return it."""
    return load_fixture("plex/plextv_shared_users.xml")


@pytest.fixture(name="session_base", scope="session")
def session_base_fixture():
    """Load the base session payload and return it."""
    return load_fixture("plex/session_base.xml")


@pytest.fixture(name="session_default", scope="session")
def session_default_fixture(session_base):
    """Load the default session payload and return it."""
    return session_base.format(user_id=1)


@pytest.fixture(name="session_new_user", scope="session")
def session_new_user_fixture(session_base):
    """Load the new user session payload and return it."""
    return session_base.format(user_id=1001)


@pytest.fixture(name="session_photo", scope="session")
def session_photo_fixture():
    """Load a photo session payload and return it."""
    return load_fixture("plex/session_photo.xml")


@pytest.fixture(name="session_plexweb", scope="session")
def session_plexweb_fixture():
    """Load a Plex Web session payload and return it."""
    return load_fixture("plex/session_plexweb.xml")


@pytest.fixture(name="session_transient", scope="session")
def session_transient_fixture():
    """Load a transient session payload and return it."""
    return load_fixture("plex/session_transient.xml")


@pytest.fixture(name="session_unknown", scope="session")
def session_unknown_fixture():
    """Load a hypothetical unknown session payload and return it."""
    return load_fixture("plex/session_unknown.xml")


@pytest.fixture(name="session_live_tv", scope="session")
def session_live_tv_fixture():
    """Load a Live TV session payload and return it."""
    return load_fixture("plex/session_live_tv.xml")


@pytest.fixture(name="livetv_sessions", scope="session")
def livetv_sessions_fixture():
    """Load livetv/sessions payload and return it."""
    return load_fixture("plex/livetv_sessions.xml")


@pytest.fixture(name="security_token", scope="session")
def security_token_fixture():
    """Load a security token payload and return it."""
    return load_fixture("plex/security_token.xml")


@pytest.fixture(name="show_seasons", scope="session")
def show_seasons_fixture():
    """Load a show's seasons payload and return it."""
    return load_fixture("plex/show_seasons.xml")


@pytest.fixture(name="sonos_resources", scope="session")
def sonos_resources_fixture():
    """Load Sonos resources payload and return it."""
    return load_fixture("plex/sonos_resources.xml")


@pytest.fixture(name="entry")
def mock_config_entry():
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )


@pytest.fixture
def mock_websocket():
    """Mock the PlexWebsocket class."""
    with patch("homeassistant.components.plex.PlexWebsocket", autospec=True) as ws:
        yield ws


@pytest.fixture
def mock_plex_calls(
    entry,
    requests_mock,
    children_20,
    children_30,
    children_200,
    children_300,
    empty_library,
    empty_payload,
    grandchildren_300,
    library,
    library_sections,
    library_movies_all,
    library_movies_sort,
    library_music_all,
    library_music_sort,
    library_tvshows_all,
    library_tvshows_sort,
    media_1,
    media_30,
    media_100,
    media_200,
    playlists,
    playlist_500,
    plextv_account,
    plextv_resources,
    plextv_shared_users,
    plex_server_accounts,
    plex_server_clients,
    plex_server_default,
    security_token,
):
    """Mock Plex API calls."""
    requests_mock.get("https://plex.tv/api/users/", text=plextv_shared_users)
    requests_mock.get("https://plex.tv/api/invites/requested", text=empty_payload)
    requests_mock.get("https://plex.tv/users/account", text=plextv_account)
    requests_mock.get("https://plex.tv/api/resources", text=plextv_resources)

    url = plex_server_url(entry)

    for server in [url, PLEX_DIRECT_URL]:
        requests_mock.get(server, text=plex_server_default)
        requests_mock.get(f"{server}/accounts", text=plex_server_accounts)

    requests_mock.get(f"{url}/clients", text=plex_server_clients)
    requests_mock.get(f"{url}/library", text=library)
    requests_mock.get(f"{url}/library/sections", text=library_sections)

    requests_mock.get(f"{url}/library/onDeck", text=empty_library)
    requests_mock.get(f"{url}/library/sections/1/sorts", text=library_movies_sort)
    requests_mock.get(f"{url}/library/sections/2/sorts", text=library_tvshows_sort)
    requests_mock.get(f"{url}/library/sections/3/sorts", text=library_music_sort)

    requests_mock.get(f"{url}/library/sections/1/all", text=library_movies_all)
    requests_mock.get(f"{url}/library/sections/2/all", text=library_tvshows_all)
    requests_mock.get(f"{url}/library/sections/3/all", text=library_music_all)

    requests_mock.get(f"{url}/library/metadata/200/children", text=children_200)
    requests_mock.get(f"{url}/library/metadata/300/children", text=children_300)
    requests_mock.get(f"{url}/library/metadata/300/allLeaves", text=grandchildren_300)

    requests_mock.get(f"{url}/library/metadata/1", text=media_1)
    requests_mock.get(f"{url}/library/metadata/30", text=media_30)
    requests_mock.get(f"{url}/library/metadata/100", text=media_100)
    requests_mock.get(f"{url}/library/metadata/200", text=media_200)

    requests_mock.get(f"{url}/library/metadata/20/children", text=children_20)
    requests_mock.get(f"{url}/library/metadata/30/children", text=children_30)

    requests_mock.get(f"{url}/playlists", text=playlists)
    requests_mock.get(f"{url}/playlists/500/items", text=playlist_500)
    requests_mock.get(f"{url}/security/token", text=security_token)


@pytest.fixture
def setup_plex_server(
    hass,
    entry,
    livetv_sessions,
    mock_websocket,
    mock_plex_calls,
    requests_mock,
    empty_payload,
    session_default,
    session_live_tv,
    session_photo,
    session_plexweb,
    session_transient,
    session_unknown,
):
    """Set up and return a mocked Plex server instance."""

    async def _wrapper(**kwargs):
        """Wrap the fixture to allow passing arguments to the setup method."""
        url = plex_server_url(entry)
        config_entry = kwargs.get("config_entry", entry)
        disable_clients = kwargs.pop("disable_clients", False)
        disable_gdm = kwargs.pop("disable_gdm", True)
        client_type = kwargs.pop("client_type", None)
        session_type = kwargs.pop("session_type", None)

        if client_type == "plexweb":
            session = session_plexweb
        elif session_type == "photo":
            session = session_photo
        elif session_type == "live_tv":
            session = session_live_tv
            requests_mock.get(f"{url}/livetv/sessions/live_tv_1", text=livetv_sessions)
        elif session_type == "transient":
            session = session_transient
        elif session_type == "unknown":
            session = session_unknown
        else:
            session = session_default

        requests_mock.get(f"{url}/status/sessions", text=session)

        if disable_clients:
            requests_mock.get(f"{url}/clients", text=empty_payload)

        with patch(
            "homeassistant.components.plex.GDM",
            return_value=MockGDM(disabled=disable_gdm),
        ):
            config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
            websocket_connected(mock_websocket)
            await hass.async_block_till_done()

        plex_server = hass.data[DOMAIN][SERVERS][entry.unique_id]
        return plex_server

    return _wrapper


@pytest.fixture
async def mock_plex_server(entry, setup_plex_server):
    """Init from a config entry and return a mocked PlexServer instance."""
    return await setup_plex_server(config_entry=entry)
