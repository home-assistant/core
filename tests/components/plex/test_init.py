"""Tests for Plex setup."""
import copy
from datetime import timedelta
from http import HTTPStatus
import ssl
from unittest.mock import patch

import plexapi
import requests
import requests_mock

import homeassistant.components.plex.const as const
from homeassistant.components.plex.models import (
    LIVE_TV_SECTION,
    TRANSIENT_SECTION,
    UNKNOWN_SECTION,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    STATE_IDLE,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .const import DEFAULT_DATA, DEFAULT_OPTIONS, PLEX_DIRECT_URL
from .helpers import trigger_plex_update, wait_for_debouncer

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_set_config_entry_unique_id(
    hass: HomeAssistant, entry, mock_plex_server
) -> None:
    """Test updating missing unique_id from config entry."""
    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert (
        hass.config_entries.async_entries(const.DOMAIN)[0].unique_id
        == mock_plex_server.machine_identifier
    )


async def test_setup_config_entry_with_error(hass: HomeAssistant, entry) -> None:
    """Test setup component from config entry with errors."""
    with patch(
        "homeassistant.components.plex.PlexServer.connect",
        side_effect=requests.exceptions.ConnectionError,
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id) is False
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY

    with patch(
        "homeassistant.components.plex.PlexServer.connect",
        side_effect=plexapi.exceptions.BadRequest,
    ):
        next_update = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_with_insecure_config_entry(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test setup component with config."""
    INSECURE_DATA = copy.deepcopy(DEFAULT_DATA)
    INSECURE_DATA[const.PLEX_SERVER_CONFIG][CONF_VERIFY_SSL] = False
    entry.data = INSECURE_DATA

    await setup_plex_server(config_entry=entry)

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED


async def test_unload_config_entry(
    hass: HomeAssistant, entry, mock_plex_server
) -> None:
    """Test unloading a config entry."""
    config_entries = hass.config_entries.async_entries(const.DOMAIN)
    assert len(config_entries) == 1
    assert entry is config_entries[0]
    assert entry.state is ConfigEntryState.LOADED

    server_id = mock_plex_server.machine_identifier
    loaded_server = hass.data[const.DOMAIN][const.SERVERS][server_id]
    assert loaded_server == mock_plex_server

    websocket = hass.data[const.DOMAIN][const.WEBSOCKETS][server_id]
    await hass.config_entries.async_unload(entry.entry_id)
    assert websocket.close.called
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_with_photo_session(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test setup component with config."""
    await setup_plex_server(session_type="photo")

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done()

    media_player = hass.states.get(
        "media_player.plex_plex_for_android_tv_shield_android_tv"
    )
    assert media_player.state == STATE_IDLE

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_server_1")
    assert sensor.state == "0"


async def test_setup_with_live_tv_session(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test setup component with a Live TV session."""
    await setup_plex_server(session_type="live_tv")

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done()

    media_player = hass.states.get(
        "media_player.plex_plex_for_android_tv_shield_android_tv"
    )
    assert media_player.state == STATE_PLAYING
    assert media_player.attributes["media_library_title"] == LIVE_TV_SECTION

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_server_1")
    assert sensor.state == "1"


async def test_setup_with_transient_session(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test setup component with a transient session."""
    await setup_plex_server(session_type="transient")

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done()

    media_player = hass.states.get(
        "media_player.plex_plex_for_android_tv_shield_android_tv"
    )
    assert media_player.state == STATE_PLAYING
    assert media_player.attributes["media_library_title"] == TRANSIENT_SECTION

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_server_1")
    assert sensor.state == "1"


async def test_setup_with_unknown_session(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test setup component with an unknown session."""
    await setup_plex_server(session_type="unknown")

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done()

    media_player = hass.states.get(
        "media_player.plex_plex_for_android_tv_shield_android_tv"
    )
    assert media_player.state == STATE_PLAYING
    assert media_player.attributes["media_library_title"] == UNKNOWN_SECTION

    await wait_for_debouncer(hass)

    sensor = hass.states.get("sensor.plex_server_1")
    assert sensor.state == "1"


async def test_setup_when_certificate_changed(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    empty_library,
    empty_payload,
    plex_server_accounts,
    plex_server_default,
    plextv_account,
    plextv_resources,
    plextv_shared_users,
    mock_websocket,
) -> None:
    """Test setup component when the Plex certificate has changed."""

    class WrongCertHostnameException(requests.exceptions.SSLError):
        """Mock the exception showing a mismatched hostname."""

        def __init__(self):
            self.__context__ = ssl.SSLCertVerificationError(
                f"hostname '{old_domain}' doesn't match"
            )

    old_domain = "1-2-3-4.1111111111ffffff1111111111ffffff.plex.direct"
    old_url = f"https://{old_domain}:32400"

    OLD_HOSTNAME_DATA = copy.deepcopy(DEFAULT_DATA)
    OLD_HOSTNAME_DATA[const.PLEX_SERVER_CONFIG][CONF_URL] = old_url

    old_entry = MockConfigEntry(
        domain=const.DOMAIN,
        data=OLD_HOSTNAME_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    requests_mock.get("https://plex.tv/api/users/", text=plextv_shared_users)
    requests_mock.get("https://plex.tv/api/invites/requested", text=empty_payload)
    requests_mock.get(old_url, exc=WrongCertHostnameException)

    # Test with account failure
    requests_mock.get(
        "https://plex.tv/users/account", status_code=HTTPStatus.UNAUTHORIZED
    )
    old_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(old_entry.entry_id) is False
    await hass.async_block_till_done()

    assert old_entry.state is ConfigEntryState.SETUP_ERROR
    await hass.config_entries.async_unload(old_entry.entry_id)

    # Test with no servers found
    requests_mock.get("https://plex.tv/users/account", text=plextv_account)
    requests_mock.get("https://plex.tv/api/resources", text=empty_payload)

    assert await hass.config_entries.async_setup(old_entry.entry_id) is False
    await hass.async_block_till_done()

    assert old_entry.state is ConfigEntryState.SETUP_ERROR
    await hass.config_entries.async_unload(old_entry.entry_id)

    # Test with success
    new_url = PLEX_DIRECT_URL
    requests_mock.get("https://plex.tv/api/resources", text=plextv_resources)
    for resource_url in [new_url, "http://1.2.3.4:32400"]:
        requests_mock.get(resource_url, text=plex_server_default)
    requests_mock.get(f"{new_url}/accounts", text=plex_server_accounts)
    requests_mock.get(f"{new_url}/library", text=empty_library)
    requests_mock.get(f"{new_url}/library/sections", text=empty_payload)

    assert await hass.config_entries.async_setup(old_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert old_entry.state is ConfigEntryState.LOADED

    assert old_entry.data[const.PLEX_SERVER_CONFIG][CONF_URL] == new_url


async def test_tokenless_server(entry, setup_plex_server) -> None:
    """Test setup with a server with token auth disabled."""
    TOKENLESS_DATA = copy.deepcopy(DEFAULT_DATA)
    TOKENLESS_DATA[const.PLEX_SERVER_CONFIG].pop(CONF_TOKEN, None)
    entry.data = TOKENLESS_DATA

    await setup_plex_server(config_entry=entry)
    assert entry.state is ConfigEntryState.LOADED


async def test_bad_token_with_tokenless_server(
    hass: HomeAssistant,
    entry,
    mock_websocket,
    setup_plex_server,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test setup with a bad token and a server with token auth disabled."""
    requests_mock.get(
        "https://plex.tv/users/account", status_code=HTTPStatus.UNAUTHORIZED
    )

    await setup_plex_server()

    assert entry.state is ConfigEntryState.LOADED

    # Ensure updates that rely on account return nothing
    trigger_plex_update(mock_websocket)
    await hass.async_block_till_done()


async def test_scan_clients_schedule(hass: HomeAssistant, setup_plex_server) -> None:
    """Test scan_clients scheduled update."""
    with patch(
        "homeassistant.components.plex.server.PlexServer._async_update_platforms"
    ) as mock_scan_clients:
        await setup_plex_server()
        mock_scan_clients.reset_mock()

        async_fire_time_changed(
            hass,
            dt_util.utcnow() + const.CLIENT_SCAN_INTERVAL,
        )
        await hass.async_block_till_done()

    assert mock_scan_clients.called


async def test_setup_with_limited_credentials(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test setup with a user with limited permissions."""
    with patch(
        "plexapi.server.PlexServer.systemAccounts",
        side_effect=plexapi.exceptions.Unauthorized,
    ) as mock_accounts:
        mock_plex_server = await setup_plex_server()

    assert mock_accounts.called

    plex_server = hass.data[const.DOMAIN][const.SERVERS][
        mock_plex_server.machine_identifier
    ]
    assert len(plex_server.accounts) == 0
    assert plex_server.owner is None

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED


async def test_trigger_reauth(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_plex_server,
    mock_websocket,
) -> None:
    """Test setup and reauthorization of a Plex token."""

    assert entry.state is ConfigEntryState.LOADED

    with patch(
        "plexapi.server.PlexServer.clients", side_effect=plexapi.exceptions.Unauthorized
    ), patch("plexapi.server.PlexServer", side_effect=plexapi.exceptions.Unauthorized):
        trigger_plex_update(mock_websocket)
        await wait_for_debouncer(hass)

    assert len(hass.config_entries.async_entries(const.DOMAIN)) == 1
    assert entry.state is not ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_setup_with_deauthorized_token(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test setup with a deauthorized token."""
    with patch(
        "plexapi.server.PlexServer",
        side_effect=plexapi.exceptions.BadRequest(const.INVALID_TOKEN_MESSAGE),
    ):
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
