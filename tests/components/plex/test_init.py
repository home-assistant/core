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
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
import homeassistant.util.dt as dt_util

from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .helpers import trigger_plex_update
from .mock_classes import MockPlexAccount, MockPlexServer

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_fire_time_changed


async def test_set_config_entry_unique_id(hass, entry, mock_plex_server):
    """Test updating missing unique_id from config entry."""
    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert (
        hass.config_entries.async_entries(const.DOMAIN)[0].unique_id
        == mock_plex_server.machineIdentifier
    )


async def test_setup_config_entry_with_error(hass, entry):
    """Test setup component from config entry with errors."""
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


async def test_setup_with_insecure_config_entry(hass, entry, setup_plex_server):
    """Test setup component with config."""
    INSECURE_DATA = copy.deepcopy(DEFAULT_DATA)
    INSECURE_DATA[const.PLEX_SERVER_CONFIG][CONF_VERIFY_SSL] = False
    entry.data = INSECURE_DATA

    await setup_plex_server(config_entry=entry)

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED


async def test_unload_config_entry(hass, entry, mock_plex_server):
    """Test unloading a config entry."""
    config_entries = hass.config_entries.async_entries(const.DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]
    assert entry.state == ENTRY_STATE_LOADED

    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[const.DOMAIN][const.SERVERS][server_id]
    assert loaded_server.plex_server == mock_plex_server

    websocket = hass.data[const.DOMAIN][const.WEBSOCKETS][server_id]
    await hass.config_entries.async_unload(entry.entry_id)
    assert websocket.close.called
    assert entry.state == ENTRY_STATE_NOT_LOADED


async def test_setup_with_photo_session(hass, entry, mock_websocket, setup_plex_server):
    """Test setup component with config."""
    mock_plex_server = await setup_plex_server(config_entry=entry, session_type="photo")

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    trigger_plex_update(mock_websocket)
    await hass.async_block_till_done()

    media_player = hass.states.get("media_player.plex_product_title")
    assert media_player.state == "idle"

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))


async def test_setup_when_certificate_changed(hass, entry):
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

    # Test with account failure
    with patch(
        "plexapi.server.PlexServer", side_effect=WrongCertHostnameException
    ), patch(
        "plexapi.myplex.MyPlexAccount", side_effect=plexapi.exceptions.Unauthorized
    ):
        old_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(old_entry.entry_id) is False
        await hass.async_block_till_done()

    assert old_entry.state == ENTRY_STATE_SETUP_ERROR
    await hass.config_entries.async_unload(old_entry.entry_id)

    # Test with no servers found
    with patch(
        "plexapi.server.PlexServer", side_effect=WrongCertHostnameException
    ), patch("plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=0)):
        assert await hass.config_entries.async_setup(old_entry.entry_id) is False
        await hass.async_block_till_done()

    assert old_entry.state == ENTRY_STATE_SETUP_ERROR
    await hass.config_entries.async_unload(old_entry.entry_id)

    # Test with success
    with patch(
        "plexapi.server.PlexServer", side_effect=WrongCertHostnameException
    ), patch("plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()):
        assert await hass.config_entries.async_setup(old_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert old_entry.state == ENTRY_STATE_LOADED

    assert (
        old_entry.data[const.PLEX_SERVER_CONFIG][CONF_URL]
        == entry.data[const.PLEX_SERVER_CONFIG][CONF_URL]
    )


async def test_tokenless_server(hass, entry, mock_websocket, setup_plex_server):
    """Test setup with a server with token auth disabled."""
    TOKENLESS_DATA = copy.deepcopy(DEFAULT_DATA)
    TOKENLESS_DATA[const.PLEX_SERVER_CONFIG].pop(CONF_TOKEN, None)
    entry.data = TOKENLESS_DATA

    await setup_plex_server(config_entry=entry)
    assert entry.state == ENTRY_STATE_LOADED


async def test_bad_token_with_tokenless_server(hass, entry):
    """Test setup with a bad token and a server with token auth disabled."""
    with patch("plexapi.server.PlexServer", return_value=MockPlexServer()), patch(
        "plexapi.myplex.MyPlexAccount", side_effect=plexapi.exceptions.Unauthorized
    ), patch(
        "homeassistant.components.plex.PlexWebsocket", autospec=True
    ) as mock_websocket:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_LOADED

    # Ensure updates that rely on account return nothing
    trigger_plex_update(mock_websocket)
    await hass.async_block_till_done()
