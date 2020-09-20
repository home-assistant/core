"""Fixtures for Plex tests."""
import pytest

from homeassistant.components.plex.const import DOMAIN

from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .mock_classes import MockPlexAccount, MockPlexServer

from tests.async_mock import patch
from tests.common import MockConfigEntry


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
def mock_plex_account():
    """Mock the PlexAccount class and return the used instance."""
    plex_account = MockPlexAccount()
    with patch("plexapi.myplex.MyPlexAccount", return_value=plex_account):
        yield plex_account


@pytest.fixture
def mock_websocket():
    """Mock the PlexWebsocket class."""
    with patch("homeassistant.components.plex.PlexWebsocket", autospec=True) as ws:
        yield ws


@pytest.fixture
def setup_plex_server(hass, entry, mock_plex_account, mock_websocket):
    """Set up and return a mocked Plex server instance."""

    async def _wrapper(**kwargs):
        """Wrap the fixture to allow passing arguments to the MockPlexServer instance."""
        config_entry = kwargs.get("config_entry", entry)
        plex_server = MockPlexServer(**kwargs)
        with patch("plexapi.server.PlexServer", return_value=plex_server):
            config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
        return plex_server

    return _wrapper


@pytest.fixture
async def mock_plex_server(entry, setup_plex_server):
    """Init from a config entry and return a mocked PlexServer instance."""
    return await setup_plex_server(config_entry=entry)
