"""Tests for Plex setup."""
import copy
from datetime import timedelta
import ssl

from asynctest import patch
import plexapi
import requests

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
import homeassistant.components.plex.const as const
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_ERROR,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import trigger_plex_update
from .const import DEFAULT_DATA, DEFAULT_OPTIONS, MOCK_SERVERS, MOCK_TOKEN
from .mock_classes import MockPlexAccount, MockPlexServer

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_with_config(hass):
    """Test setup component with config."""
    config = {
        const.DOMAIN: {
            CONF_HOST: MOCK_SERVERS[0][CONF_HOST],
            CONF_PORT: MOCK_SERVERS[0][CONF_PORT],
            CONF_TOKEN: MOCK_TOKEN,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
            MP_DOMAIN: {
                const.CONF_IGNORE_NEW_SHARED_USERS: False,
                const.CONF_USE_EPISODE_ART: False,
            },
        },
    }

    mock_plex_server = MockPlexServer()

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket.listen"
    ) as mock_listen:
        assert await async_setup_component(hass, const.DOMAIN, config) is True
        await hass.async_block_till_done()

    assert mock_listen.called
    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    entry = hass.config_entries.async_entries(const.DOMAIN)[0]
    assert entry.state == ENTRY_STATE_LOADED

    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[const.DOMAIN][const.SERVERS][server_id]

    assert loaded_server.plex_server == mock_plex_server

    assert server_id in hass.data[const.DOMAIN][const.DISPATCHERS]
    assert server_id in hass.data[const.DOMAIN][const.WEBSOCKETS]
    assert (
        hass.data[const.DOMAIN][const.PLATFORMS_COMPLETED][server_id] == const.PLATFORMS
    )


async def test_setup_with_config_entry(hass, caplog):
    """Test setup component with config."""

    mock_plex_server = MockPlexServer()

    entry = MockConfigEntry(
        domain=const.DOMAIN,
        data=DEFAULT_DATA,
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

    server_id = mock_plex_server.machineIdentifier
    loaded_server = hass.data[const.DOMAIN][const.SERVERS][server_id]

    assert loaded_server.plex_server == mock_plex_server

    assert server_id in hass.data[const.DOMAIN][const.DISPATCHERS]
    assert server_id in hass.data[const.DOMAIN][const.WEBSOCKETS]
    assert (
        hass.data[const.DOMAIN][const.PLATFORMS_COMPLETED][server_id] == const.PLATFORMS
    )

    await trigger_plex_update(hass, server_id)

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    await trigger_plex_update(hass, server_id)

    with patch.object(
        mock_plex_server, "clients", side_effect=plexapi.exceptions.BadRequest
    ) as patched_clients_bad_request:
        await trigger_plex_update(hass, server_id)

    assert patched_clients_bad_request.called
    assert "Error requesting Plex client data from server" in caplog.text

    with patch.object(
        mock_plex_server, "clients", side_effect=requests.exceptions.RequestException
    ) as patched_clients_requests_exception:
        await trigger_plex_update(hass, server_id)

    assert patched_clients_requests_exception.called
    assert (
        f"Could not connect to Plex server: {mock_plex_server.friendlyName}"
        in caplog.text
    )


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

    assert server_id in hass.data[const.DOMAIN][const.DISPATCHERS]
    assert server_id in hass.data[const.DOMAIN][const.WEBSOCKETS]
    assert (
        hass.data[const.DOMAIN][const.PLATFORMS_COMPLETED][server_id] == const.PLATFORMS
    )

    with patch("homeassistant.components.plex.PlexWebsocket.close") as mock_close:
        await hass.config_entries.async_unload(entry.entry_id)
        assert mock_close.called

    assert entry.state == ENTRY_STATE_NOT_LOADED

    assert server_id not in hass.data[const.DOMAIN][const.SERVERS]
    assert server_id not in hass.data[const.DOMAIN][const.DISPATCHERS]
    assert server_id not in hass.data[const.DOMAIN][const.WEBSOCKETS]


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

    await trigger_plex_update(hass, server_id)

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
