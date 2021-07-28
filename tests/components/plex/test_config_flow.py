"""Tests for Plex config flow."""
import copy
import ssl
from unittest.mock import patch

import plexapi.exceptions
import pytest
import requests.exceptions

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.plex import config_flow
from homeassistant.components.plex.const import (
    AUTOMATIC_SETUP_STRING,
    CONF_IGNORE_NEW_SHARED_USERS,
    CONF_IGNORE_PLEX_WEB_CLIENTS,
    CONF_MONITORED_USERS,
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    CONF_USE_EPISODE_ART,
    DOMAIN,
    MANUAL_SETUP_STRING,
    PLEX_SERVER_CONFIG,
    SERVERS,
)
from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_REAUTH,
    SOURCE_USER,
    ConfigEntryState,
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

from .const import DEFAULT_OPTIONS, MOCK_SERVERS, MOCK_TOKEN, PLEX_DIRECT_URL
from .helpers import trigger_plex_update, wait_for_debouncer
from .mock_classes import MockGDM

from tests.common import MockConfigEntry


async def test_bad_credentials(hass, current_request_with_host):
    """Test when provided credentials are rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "plexapi.myplex.MyPlexAccount", side_effect=plexapi.exceptions.Unauthorized
    ), patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value="BAD TOKEN"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"][CONF_TOKEN] == "faulty_credentials"


async def test_bad_hostname(hass, mock_plex_calls, current_request_with_host):
    """Test when an invalid address is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "plexapi.myplex.MyPlexResource.connect",
        side_effect=requests.exceptions.ConnectionError,
    ), patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"][CONF_HOST] == "not_found"


async def test_unknown_exception(hass, current_request_with_host):
    """Test when an unknown exception is encountered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("plexapi.myplex.MyPlexAccount", side_effect=Exception), patch(
        "plexauth.PlexAuth.initiate_auth"
    ), patch("plexauth.PlexAuth.token", return_value="MOCK_TOKEN"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "abort"
        assert result["reason"] == "unknown"


async def test_no_servers_found(
    hass, mock_plex_calls, requests_mock, empty_payload, current_request_with_host
):
    """Test when no servers are on an account."""
    requests_mock.get("https://plex.tv/api/resources", text=empty_payload)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "no_servers"


async def test_single_available_server(
    hass, mock_plex_calls, current_request_with_host
):
    """Test creating an entry with one server available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "create_entry"

        server_id = result["data"][CONF_SERVER_IDENTIFIER]
        mock_plex_server = hass.data[DOMAIN][SERVERS][server_id]

        assert result["title"] == mock_plex_server.url_in_use
        assert result["data"][CONF_SERVER] == mock_plex_server.friendly_name
        assert (
            result["data"][CONF_SERVER_IDENTIFIER]
            == mock_plex_server.machine_identifier
        )
        assert (
            result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server.url_in_use
        )
        assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_multiple_servers_with_selection(
    hass,
    mock_plex_calls,
    requests_mock,
    plextv_resources_base,
    current_request_with_host,
):
    """Test creating an entry with multiple servers available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    requests_mock.get(
        "https://plex.tv/api/resources",
        text=plextv_resources_base.format(second_server_enabled=1),
    )
    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "form"
        assert result["step_id"] == "select_server"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SERVER: MOCK_SERVERS[0][CONF_SERVER]},
        )
        assert result["type"] == "create_entry"

        server_id = result["data"][CONF_SERVER_IDENTIFIER]
        mock_plex_server = hass.data[DOMAIN][SERVERS][server_id]

        assert result["title"] == mock_plex_server.url_in_use
        assert result["data"][CONF_SERVER] == mock_plex_server.friendly_name
        assert (
            result["data"][CONF_SERVER_IDENTIFIER]
            == mock_plex_server.machine_identifier
        )
        assert (
            result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server.url_in_use
        )
        assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_adding_last_unconfigured_server(
    hass,
    mock_plex_calls,
    requests_mock,
    plextv_resources_base,
    current_request_with_host,
):
    """Test automatically adding last unconfigured server when multiple servers on account."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERVER_IDENTIFIER: MOCK_SERVERS[1][CONF_SERVER_IDENTIFIER],
            CONF_SERVER: MOCK_SERVERS[1][CONF_SERVER],
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    requests_mock.get(
        "https://plex.tv/api/resources",
        text=plextv_resources_base.format(second_server_enabled=1),
    )

    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "create_entry"

        server_id = result["data"][CONF_SERVER_IDENTIFIER]
        mock_plex_server = hass.data[DOMAIN][SERVERS][server_id]

        assert result["title"] == mock_plex_server.url_in_use
        assert result["data"][CONF_SERVER] == mock_plex_server.friendly_name
        assert (
            result["data"][CONF_SERVER_IDENTIFIER]
            == mock_plex_server.machine_identifier
        )
        assert (
            result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server.url_in_use
        )
        assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_all_available_servers_configured(
    hass,
    entry,
    requests_mock,
    plextv_account,
    plextv_resources_base,
    current_request_with_host,
):
    """Test when all available servers are already configured."""
    entry.add_to_hass(hass)

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERVER_IDENTIFIER: MOCK_SERVERS[1][CONF_SERVER_IDENTIFIER],
            CONF_SERVER: MOCK_SERVERS[1][CONF_SERVER],
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    requests_mock.get("https://plex.tv/users/account", text=plextv_account)
    requests_mock.get(
        "https://plex.tv/api/resources",
        text=plextv_resources_base.format(second_server_enabled=1),
    )

    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "abort"
        assert result["reason"] == "all_configured"


async def test_option_flow(hass, entry, mock_plex_server):
    """Test config options flow selection."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == "form"
    assert result["step_id"] == "plex_mp_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_EPISODE_ART: True,
            CONF_IGNORE_NEW_SHARED_USERS: True,
            CONF_MONITORED_USERS: list(mock_plex_server.accounts),
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        MP_DOMAIN: {
            CONF_USE_EPISODE_ART: True,
            CONF_IGNORE_NEW_SHARED_USERS: True,
            CONF_MONITORED_USERS: {
                user: {"enabled": True} for user in mock_plex_server.accounts
            },
            CONF_IGNORE_PLEX_WEB_CLIENTS: False,
        }
    }


async def test_missing_option_flow(hass, entry, mock_plex_server):
    """Test config options flow selection when no options stored."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == "form"
    assert result["step_id"] == "plex_mp_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_EPISODE_ART: True,
            CONF_IGNORE_NEW_SHARED_USERS: True,
            CONF_MONITORED_USERS: list(mock_plex_server.accounts),
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        MP_DOMAIN: {
            CONF_USE_EPISODE_ART: True,
            CONF_IGNORE_NEW_SHARED_USERS: True,
            CONF_MONITORED_USERS: {
                user: {"enabled": True} for user in mock_plex_server.accounts
            },
            CONF_IGNORE_PLEX_WEB_CLIENTS: False,
        }
    }


async def test_option_flow_new_users_available(hass, entry, setup_plex_server):
    """Test config options multiselect defaults when new Plex users are seen."""
    OPTIONS_OWNER_ONLY = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_OWNER_ONLY[MP_DOMAIN][CONF_MONITORED_USERS] = {"User 1": {"enabled": True}}
    entry.options = OPTIONS_OWNER_ONLY

    mock_plex_server = await setup_plex_server(config_entry=entry)
    await hass.async_block_till_done()

    server_id = mock_plex_server.machine_identifier
    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    new_users = [x for x in mock_plex_server.accounts if x not in monitored_users]
    assert len(monitored_users) == 1
    assert len(new_users) == 2

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == "form"
    assert result["step_id"] == "plex_mp_settings"
    multiselect_defaults = result["data_schema"].schema["monitored_users"].options

    assert "[Owner]" in multiselect_defaults["User 1"]
    for user in new_users:
        assert "[New]" in multiselect_defaults[user]


async def test_external_timed_out(hass, current_request_with_host):
    """Test when external flow times out."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=None
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "abort"
        assert result["reason"] == "token_request_timeout"


async def test_callback_view(hass, aiohttp_client, current_request_with_host):
    """Test callback view."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == "external"

        client = await aiohttp_client(hass.http.app)
        forward_url = f'{config_flow.AUTH_CALLBACK_PATH}?flow_id={result["flow_id"]}'

        resp = await client.get(forward_url)
        assert resp.status == 200


async def test_manual_config(hass, mock_plex_calls, current_request_with_host):
    """Test creating via manual configuration."""

    class WrongCertValidaitionException(requests.exceptions.SSLError):
        """Mock the exception showing an unmatched error."""

        def __init__(self):
            self.__context__ = ssl.SSLCertVerificationError(
                "some random message that doesn't match"
            )

    # Basic mode
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["data_schema"] is None
    hass.config_entries.flow.async_abort(result["flow_id"])

    # Advanced automatic
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    assert result["data_schema"] is not None
    assert result["type"] == "form"
    assert result["step_id"] == "user_advanced"

    with patch("plexauth.PlexAuth.initiate_auth"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"setup_method": AUTOMATIC_SETUP_STRING}
        )

    assert result["type"] == "external"
    hass.config_entries.flow.async_abort(result["flow_id"])

    # Advanced manual
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    assert result["data_schema"] is not None
    assert result["type"] == "form"
    assert result["step_id"] == "user_advanced"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"setup_method": MANUAL_SETUP_STRING}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual_setup"

    MANUAL_SERVER = {
        CONF_HOST: MOCK_SERVERS[0][CONF_HOST],
        CONF_PORT: MOCK_SERVERS[0][CONF_PORT],
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
        CONF_TOKEN: MOCK_TOKEN,
    }

    MANUAL_SERVER_NO_HOST_OR_TOKEN = {
        CONF_PORT: MOCK_SERVERS[0][CONF_PORT],
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MANUAL_SERVER_NO_HOST_OR_TOKEN
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual_setup"
    assert result["errors"]["base"] == "host_or_token"

    with patch(
        "plexapi.server.PlexServer",
        side_effect=requests.exceptions.SSLError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )

    assert result["type"] == "form"
    assert result["step_id"] == "manual_setup"
    assert result["errors"]["base"] == "ssl_error"

    with patch(
        "plexapi.server.PlexServer",
        side_effect=WrongCertValidaitionException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )

    assert result["type"] == "form"
    assert result["step_id"] == "manual_setup"
    assert result["errors"]["base"] == "ssl_error"

    with patch(
        "homeassistant.components.plex.PlexServer.connect",
        side_effect=requests.exceptions.SSLError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )

    assert result["type"] == "form"
    assert result["step_id"] == "manual_setup"
    assert result["errors"]["base"] == "ssl_error"

    with patch("homeassistant.components.plex.PlexWebsocket", autospec=True), patch(
        "homeassistant.components.plex.GDM", return_value=MockGDM(disabled=True)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"

    server_id = result["data"][CONF_SERVER_IDENTIFIER]
    mock_plex_server = hass.data[DOMAIN][SERVERS][server_id]

    assert result["title"] == mock_plex_server.url_in_use
    assert result["data"][CONF_SERVER] == mock_plex_server.friendly_name
    assert result["data"][CONF_SERVER_IDENTIFIER] == mock_plex_server.machine_identifier
    assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server.url_in_use
    assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_manual_config_with_token(
    hass, mock_plex_calls, requests_mock, empty_library, empty_payload
):
    """Test creating via manual configuration with only token."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user_advanced"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"setup_method": MANUAL_SETUP_STRING}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual_setup"

    with patch(
        "homeassistant.components.plex.GDM", return_value=MockGDM(disabled=True)
    ), patch("homeassistant.components.plex.PlexWebsocket", autospec=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: MOCK_TOKEN}
        )

    assert result["type"] == "create_entry"

    server_id = result["data"][CONF_SERVER_IDENTIFIER]
    mock_plex_server = hass.data[DOMAIN][SERVERS][server_id]
    mock_url = mock_plex_server.url_in_use

    assert result["title"] == mock_url
    assert result["data"][CONF_SERVER] == mock_plex_server.friendly_name
    assert result["data"][CONF_SERVER_IDENTIFIER] == mock_plex_server.machine_identifier
    assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_url
    assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN

    # Complete Plex integration setup before teardown
    requests_mock.get(f"{mock_url}/library", text=empty_library)
    requests_mock.get(f"{mock_url}/library/sections", text=empty_payload)
    await hass.async_block_till_done()


async def test_setup_with_limited_credentials(hass, entry, setup_plex_server):
    """Test setup with a user with limited permissions."""
    with patch(
        "plexapi.server.PlexServer.systemAccounts",
        side_effect=plexapi.exceptions.Unauthorized,
    ) as mock_accounts:
        mock_plex_server = await setup_plex_server()

    assert mock_accounts.called

    plex_server = hass.data[DOMAIN][SERVERS][mock_plex_server.machine_identifier]
    assert len(plex_server.accounts) == 0
    assert plex_server.owner is None

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED


async def test_integration_discovery(hass):
    """Test integration self-discovery."""
    mock_gdm = MockGDM()

    with patch("homeassistant.components.plex.config_flow.GDM", return_value=mock_gdm):
        await config_flow.async_discover(hass)

    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1

    flow = flows[0]

    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY
    assert (
        flow["context"]["unique_id"]
        == mock_gdm.entries[0]["data"]["Resource-Identifier"]
    )
    assert flow["step_id"] == "user"


async def test_trigger_reauth(
    hass, entry, mock_plex_server, mock_websocket, current_request_with_host
):
    """Test setup and reauthorization of a Plex token."""
    await async_setup_component(hass, "persistent_notification", {})

    assert entry.state is ConfigEntryState.LOADED

    with patch(
        "plexapi.server.PlexServer.clients", side_effect=plexapi.exceptions.Unauthorized
    ), patch("plexapi.server.PlexServer", side_effect=plexapi.exceptions.Unauthorized):
        trigger_plex_update(mock_websocket)
        await wait_for_debouncer(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is not ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH

    flow_id = flows[0]["flow_id"]

    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value="BRAND_NEW_TOKEN"
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"
        assert result["flow_id"] == flow_id

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_SERVER] == mock_plex_server.friendly_name
    assert entry.data[CONF_SERVER_IDENTIFIER] == mock_plex_server.machine_identifier
    assert entry.data[PLEX_SERVER_CONFIG][CONF_URL] == PLEX_DIRECT_URL
    assert entry.data[PLEX_SERVER_CONFIG][CONF_TOKEN] == "BRAND_NEW_TOKEN"


async def test_client_request_missing(hass):
    """Test when client headers are not set properly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=None
    ):
        with pytest.raises(RuntimeError):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )


async def test_client_header_issues(hass, current_request_with_host):
    """Test when client headers are not set properly."""

    class MockRequest:
        headers = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=None
    ), patch(
        "homeassistant.components.http.current_request.get", return_value=MockRequest()
    ):
        with pytest.raises(RuntimeError):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )
