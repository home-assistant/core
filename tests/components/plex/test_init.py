"""Tests for Plex setup."""
import copy
from datetime import timedelta
import ssl

import plexapi
import requests

import homeassistant.components.plex.const as const
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_ERROR,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .mock_classes import MockPlexAccount, MockPlexServer

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_fire_time_changed

# class TestClockedPlex(ClockedTestCase):
#     """Create clock-controlled tests.async_mock class."""

#     @pytest.fixture(autouse=True)
#     def inject_fixture(self, caplog, hass_storage):
#         """Inject pytest fixtures as instance attributes."""
#         self.caplog = caplog

#     async def setUp(self):
#         """Initialize this test class."""
#         self.hass = await async_test_home_assistant(self.loop)

#     async def tearDown(self):
#         """Clean up the HomeAssistant instance."""
#         await self.hass.async_stop()

#     async def test_setup_with_config_entry(self):
#         """Test setup component with config."""
#         hass = self.hass

#         mock_plex_server = MockPlexServer()

#         entry = MockConfigEntry(
#             domain=const.DOMAIN,
#             data=DEFAULT_DATA,
#             options=DEFAULT_OPTIONS,
#             unique_id=DEFAULT_DATA["server_id"],
#         )

#         with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
#             "homeassistant.components.plex.PlexWebsocket.listen"
#         ) as mock_listen:
#             entry.add_to_hass(hass)
#             assert await hass.config_entries.async_setup(entry.entry_id)
#             await hass.async_block_till_done()

#         assert mock_listen.called

#         assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
#         assert entry.state == ENTRY_STATE_LOADED

#         server_id = mock_plex_server.machineIdentifier
#         loaded_server = hass.data[const.DOMAIN][const.SERVERS][server_id]

#         assert loaded_server.plex_server == mock_plex_server

#         async_dispatcher_send(
#             hass, const.PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id)
#         )
#         await hass.async_block_till_done()

#         sensor = hass.states.get("sensor.plex_plex_server_1")
#         assert sensor.state == str(len(mock_plex_server.accounts))

#         # Ensure existing entities refresh
#         await self.advance(const.DEBOUNCE_TIMEOUT)
#         async_dispatcher_send(
#             hass, const.PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id)
#         )
#         await hass.async_block_till_done()

#         for test_exception in (
#             plexapi.exceptions.BadRequest,
#             requests.exceptions.RequestException,
#         ):
#             with patch.object(
#                 mock_plex_server, "clients", side_effect=test_exception
#             ) as patched_clients_bad_request:
#                 await self.advance(const.DEBOUNCE_TIMEOUT)
#                 async_dispatcher_send(
#                     hass, const.PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id)
#                 )
#                 await hass.async_block_till_done()

#             assert patched_clients_bad_request.called
#             assert (
#                 f"Could not connect to Plex server: {mock_plex_server.friendlyName}"
#                 in self.caplog.text
#             )
#             self.caplog.clear()


async def test_set_config_entry_unique_id(hass):
    """Test updating missing unique_id from config entry."""

    mock_plex_server = MockPlexServer()

    entry = MockConfigEntry(
        domain=const.DOMAIN, data=DEFAULT_DATA, options=DEFAULT_OPTIONS, unique_id=None,
    )

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ) as mock_listen:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_listen.called

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert (
        hass.config_entries.async_entries(const.DOMAIN)[0].unique_id
        == mock_plex_server.machineIdentifier
    )


async def test_setup_config_entry_with_error(hass):
    """Test setup component from config entry with errors."""

    entry = MockConfigEntry(
        domain=const.DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    with patch(
        "homeassistant.components.plex.PlexServer.connect",
        side_effect=requests.exceptions.ConnectionError,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id) is False
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_SETUP_RETRY

    with patch(
        "homeassistant.components.plex.PlexServer.connect",
        side_effect=plexapi.exceptions.BadRequest,
    ):
        next_update = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_SETUP_ERROR


async def test_setup_with_insecure_config_entry(hass):
    """Test setup component with config."""

    mock_plex_server = MockPlexServer()

    INSECURE_DATA = copy.deepcopy(DEFAULT_DATA)
    INSECURE_DATA[const.PLEX_SERVER_CONFIG][CONF_VERIFY_SSL] = False

    entry = MockConfigEntry(
        domain=const.DOMAIN,
        data=INSECURE_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ) as mock_listen:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_listen.called

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED


async def test_unload_config_entry(hass):
    """Test unloading a config entry."""
    mock_plex_server = MockPlexServer()

    entry = MockConfigEntry(
        domain=const.DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )
    entry.add_to_hass(hass)

    config_entries = hass.config_entries.async_entries(const.DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ) as mock_listen:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_listen.called

    assert entry.state == ENTRY_STATE_LOADED

    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[const.DOMAIN][const.SERVERS][server_id]

    assert loaded_server.plex_server == mock_plex_server

    with patch("homeassistant.components.plex.PlexWebsocket.close") as mock_close:
        await hass.config_entries.async_unload(entry.entry_id)
        assert mock_close.called

    assert entry.state == ENTRY_STATE_NOT_LOADED


async def test_setup_with_photo_session(hass):
    """Test setup component with config."""

    mock_plex_server = MockPlexServer(session_type="photo")

    entry = MockConfigEntry(
        domain=const.DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    server_id = mock_plex_server.machineIdentifier

    with patch("plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()):
        async_dispatcher_send(
            hass, const.PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id)
        )
        await hass.async_block_till_done()

    media_player = hass.states.get("media_player.plex_product_title")
    assert media_player.state == "idle"

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))


async def test_setup_when_certificate_changed(hass):
    """Test setup component when the Plex certificate has changed."""

    old_domain = "1-2-3-4.1234567890abcdef1234567890abcdef.plex.direct"
    old_url = f"https://{old_domain}:32400"

    OLD_HOSTNAME_DATA = copy.deepcopy(DEFAULT_DATA)
    OLD_HOSTNAME_DATA[const.PLEX_SERVER_CONFIG][CONF_URL] = old_url

    class WrongCertHostnameException(requests.exceptions.SSLError):
        """Mock the exception showing a mismatched hostname."""

        def __init__(self):
            self.__context__ = ssl.SSLCertVerificationError(
                f"hostname '{old_domain}' doesn't match"
            )

    old_entry = MockConfigEntry(
        domain=const.DOMAIN,
        data=OLD_HOSTNAME_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    new_entry = MockConfigEntry(domain=const.DOMAIN, data=DEFAULT_DATA)

    with patch(
        "plexapi.server.PlexServer", side_effect=WrongCertHostnameException
    ), patch("plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()):
        old_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(old_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert old_entry.state == ENTRY_STATE_LOADED

    assert (
        old_entry.data[const.PLEX_SERVER_CONFIG][CONF_URL]
        == new_entry.data[const.PLEX_SERVER_CONFIG][CONF_URL]
    )
