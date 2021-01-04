"""Fixtures for Plex tests."""
from unittest.mock import patch

import pytest

from homeassistant.components.plex.const import DOMAIN, PLEX_SERVER_CONFIG, SERVERS
from homeassistant.const import CONF_URL

from .const import DEFAULT_DATA, DEFAULT_OPTIONS, PLEX_DIRECT_URL
from .helpers import websocket_connected
from .mock_classes import MockGDM
from .payloads import (
    CHILDREN_20,
    CHILDREN_30,
    CHILDREN_200,
    CHILDREN_300,
    DEFAULT_SESSION,
    EMPTY_LIBRARY,
    EMPTY_PAYLOAD,
    GRANDCHILDREN_300,
    LIBRARY_MOVIES_ALL,
    LIBRARY_MOVIES_SORT,
    LIBRARY_MUSIC_ALL,
    LIBRARY_MUSIC_SORT,
    LIBRARY_TVSHOWS_ALL,
    LIBRARY_TVSHOWS_SORT,
    MEDIA_1,
    MEDIA_30,
    MEDIA_100,
    MEDIA_200,
    PHOTO_SESSION,
    PLAYLIST_500,
    PLAYLISTS_PAYLOAD,
    PLEX_SERVER_PAYLOAD,
    PLEXTV_ACCOUNT_PAYLOAD,
    PLEXTV_RESOURCES,
    PLEXWEB_SESSION,
    PMS_ACCOUNT_PAYLOAD,
    PMS_CLIENTS,
    PMS_LIBRARY_PAYLOAD,
    PMS_LIBRARY_SECTIONS_PAYLOAD,
    SECURITY_TOKEN,
)

from tests.common import MockConfigEntry


def plex_server_url(entry):
    """Return a protocol-less URL from a config entry."""
    return entry.data[PLEX_SERVER_CONFIG][CONF_URL].split(":", 1)[-1]


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
def mock_plex_calls(entry, requests_mock):
    """Mock Plex API calls."""
    requests_mock.get("https://plex.tv/users/account", text=PLEXTV_ACCOUNT_PAYLOAD)
    requests_mock.get("https://plex.tv/api/resources", text=PLEXTV_RESOURCES)

    url = plex_server_url(entry)

    for server in [url, PLEX_DIRECT_URL]:
        requests_mock.get(server, text=PLEX_SERVER_PAYLOAD)
        requests_mock.get(f"{server}/accounts", text=PMS_ACCOUNT_PAYLOAD)

    requests_mock.get(f"{url}/clients", text=PMS_CLIENTS)
    requests_mock.get(f"{url}/library", text=PMS_LIBRARY_PAYLOAD)
    requests_mock.get(f"{url}/library/sections", text=PMS_LIBRARY_SECTIONS_PAYLOAD)

    requests_mock.get(f"{url}/library/onDeck", text=EMPTY_LIBRARY)
    requests_mock.get(f"{url}/library/sections/1/sorts", text=LIBRARY_MOVIES_SORT)
    requests_mock.get(f"{url}/library/sections/2/sorts", text=LIBRARY_TVSHOWS_SORT)
    requests_mock.get(f"{url}/library/sections/3/sorts", text=LIBRARY_MUSIC_SORT)

    requests_mock.get(f"{url}/library/sections/1/all", text=LIBRARY_MOVIES_ALL)
    requests_mock.get(f"{url}/library/sections/2/all", text=LIBRARY_TVSHOWS_ALL)
    requests_mock.get(f"{url}/library/sections/3/all", text=LIBRARY_MUSIC_ALL)

    requests_mock.get(f"{url}/library/metadata/200/children", text=CHILDREN_200)
    requests_mock.get(f"{url}/library/metadata/300/children", text=CHILDREN_300)
    requests_mock.get(f"{url}/library/metadata/300/allLeaves", text=GRANDCHILDREN_300)

    requests_mock.get(f"{url}/library/metadata/1", text=MEDIA_1)
    requests_mock.get(f"{url}/library/metadata/30", text=MEDIA_30)
    requests_mock.get(f"{url}/library/metadata/100", text=MEDIA_100)
    requests_mock.get(f"{url}/library/metadata/200", text=MEDIA_200)

    requests_mock.get(f"{url}/library/metadata/20/children", text=CHILDREN_20)
    requests_mock.get(f"{url}/library/metadata/30/children", text=CHILDREN_30)

    requests_mock.get(f"{url}/playlists", text=PLAYLISTS_PAYLOAD)
    requests_mock.get(f"{url}/playlists/500/items", text=PLAYLIST_500)
    requests_mock.get(f"{url}/security/token", text=SECURITY_TOKEN)


@pytest.fixture
def setup_plex_server(hass, entry, mock_websocket, mock_plex_calls, requests_mock):
    """Set up and return a mocked Plex server instance."""

    async def _wrapper(**kwargs):
        """Wrap the fixture to allow passing arguments to the setup method."""
        config_entry = kwargs.get("config_entry", entry)
        disable_clients = kwargs.pop("disable_clients", False)
        disable_gdm = kwargs.pop("disable_gdm", True)
        client_type = kwargs.pop("client_type", None)
        session_type = kwargs.pop("session_type", None)

        if client_type == "plexweb":
            session = PLEXWEB_SESSION
        elif session_type == "photo":
            session = PHOTO_SESSION
        else:
            session = DEFAULT_SESSION

        url = plex_server_url(entry)
        requests_mock.get(f"{url}/status/sessions", text=session)

        if disable_clients:
            requests_mock.get(f"{url}/clients", text=EMPTY_PAYLOAD)

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
