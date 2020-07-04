"""Tests for Plex config flow."""
import copy
import ssl

import plexapi.exceptions
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
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    SOURCE_INTEGRATION_DISCOVERY,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
)

from .const import DEFAULT_DATA, DEFAULT_OPTIONS, MOCK_SERVERS, MOCK_TOKEN
from .helpers import trigger_plex_update
from .mock_classes import MockGDM, MockPlexAccount, MockPlexServer, MockResource

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_bad_credentials(hass):
    """Test when provided credentials are rejected."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
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


async def test_bad_hostname(hass):
    """Test when an invalid address is provided."""
    mock_plex_account = MockPlexAccount()

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=mock_plex_account
    ), patch.object(
        MockResource, "connect", side_effect=requests.exceptions.ConnectionError
    ), patch(
        "plexauth.PlexAuth.initiate_auth"
    ), patch(
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


async def test_unknown_exception(hass):
    """Test when an unknown exception is encountered."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
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


async def test_no_servers_found(hass):
    """Test when no servers are on an account."""

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=0)
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
        assert result["errors"]["base"] == "no_servers"


async def test_single_available_server(hass):
    """Test creating an entry with one server available."""

    mock_plex_server = MockPlexServer()

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()), patch(
        "plexapi.server.PlexServer", return_value=mock_plex_server
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
        assert result["type"] == "create_entry"
        assert result["title"] == mock_plex_server.friendlyName
        assert result["data"][CONF_SERVER] == mock_plex_server.friendlyName
        assert (
            result["data"][CONF_SERVER_IDENTIFIER] == mock_plex_server.machineIdentifier
        )
        assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server._baseurl
        assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_multiple_servers_with_selection(hass):
    """Test creating an entry with multiple servers available."""

    mock_plex_server = MockPlexServer()

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=2)
    ), patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexauth.PlexAuth.initiate_auth"
    ), patch(
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
            result["flow_id"], user_input={CONF_SERVER: MOCK_SERVERS[0][CONF_SERVER]},
        )
        assert result["type"] == "create_entry"
        assert result["title"] == mock_plex_server.friendlyName
        assert result["data"][CONF_SERVER] == mock_plex_server.friendlyName
        assert (
            result["data"][CONF_SERVER_IDENTIFIER] == mock_plex_server.machineIdentifier
        )
        assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server._baseurl
        assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_adding_last_unconfigured_server(hass):
    """Test automatically adding last unconfigured server when multiple servers on account."""

    mock_plex_server = MockPlexServer()

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERVER_IDENTIFIER: MOCK_SERVERS[1][CONF_SERVER_IDENTIFIER],
            CONF_SERVER: MOCK_SERVERS[1][CONF_SERVER],
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=2)
    ), patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexauth.PlexAuth.initiate_auth"
    ), patch(
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
        assert result["title"] == mock_plex_server.friendlyName
        assert result["data"][CONF_SERVER] == mock_plex_server.friendlyName
        assert (
            result["data"][CONF_SERVER_IDENTIFIER] == mock_plex_server.machineIdentifier
        )
        assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server._baseurl
        assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_all_available_servers_configured(hass):
    """Test when all available servers are already configured."""

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERVER_IDENTIFIER: MOCK_SERVERS[0][CONF_SERVER_IDENTIFIER],
            CONF_SERVER: MOCK_SERVERS[0][CONF_SERVER],
        },
    ).add_to_hass(hass)

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERVER_IDENTIFIER: MOCK_SERVERS[1][CONF_SERVER_IDENTIFIER],
            CONF_SERVER: MOCK_SERVERS[1][CONF_SERVER],
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=2)
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
        assert result["type"] == "abort"
        assert result["reason"] == "all_configured"


async def test_option_flow(hass):
    """Test config options flow selection."""
    mock_plex_server = MockPlexServer()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket", autospec=True):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

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


async def test_missing_option_flow(hass):
    """Test config options flow selection when no options stored."""
    mock_plex_server = MockPlexServer()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=None,
        unique_id=DEFAULT_DATA["server_id"],
    )

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch("homeassistant.components.plex.PlexWebsocket", autospec=True):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

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


async def test_option_flow_new_users_available(hass, caplog):
    """Test config options multiselect defaults when new Plex users are seen."""

    OPTIONS_OWNER_ONLY = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_OWNER_ONLY[MP_DOMAIN][CONF_MONITORED_USERS] = {"Owner": {"enabled": True}}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=OPTIONS_OWNER_ONLY,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch(
        "homeassistant.components.plex.PlexWebsocket", autospec=True
    ) as mock_websocket:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    trigger_plex_update(mock_websocket)
    await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier
    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    new_users = [x for x in mock_plex_server.accounts if x not in monitored_users]
    assert len(monitored_users) == 1
    assert len(new_users) == 2

    sensor = hass.states.get("sensor.plex_plex_server_1")
    assert sensor.state == str(len(mock_plex_server.accounts))

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == "form"
    assert result["step_id"] == "plex_mp_settings"
    multiselect_defaults = result["data_schema"].schema["monitored_users"].options

    assert "[Owner]" in multiselect_defaults["Owner"]
    for user in new_users:
        assert "[New]" in multiselect_defaults[user]


async def test_external_timed_out(hass):
    """Test when external flow times out."""

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
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


async def test_callback_view(hass, aiohttp_client):
    """Test callback view."""

    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
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


async def test_manual_config(hass):
    """Test creating via manual configuration."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"},
    )

    class WrongCertValidaitionException(requests.exceptions.SSLError):
        """Mock the exception showing an unmatched error."""

        def __init__(self):
            self.__context__ = ssl.SSLCertVerificationError(
                "some random message that doesn't match"
            )

    # Basic mode
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["data_schema"] is None
    hass.config_entries.flow.async_abort(result["flow_id"])

    # Advanced automatic
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user", "show_advanced_options": True}
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
        config_flow.DOMAIN, context={"source": "user", "show_advanced_options": True}
    )

    assert result["data_schema"] is not None
    assert result["type"] == "form"
    assert result["step_id"] == "user_advanced"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"setup_method": MANUAL_SETUP_STRING}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual_setup"

    mock_plex_server = MockPlexServer()

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
        "plexapi.server.PlexServer", side_effect=requests.exceptions.SSLError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )

    assert result["type"] == "form"
    assert result["step_id"] == "manual_setup"
    assert result["errors"]["base"] == "ssl_error"

    with patch(
        "plexapi.server.PlexServer", side_effect=WrongCertValidaitionException,
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

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.PlexWebsocket", autospec=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )

    assert result["type"] == "create_entry"
    assert result["title"] == mock_plex_server.friendlyName
    assert result["data"][CONF_SERVER] == mock_plex_server.friendlyName
    assert result["data"][CONF_SERVER_IDENTIFIER] == mock_plex_server.machineIdentifier
    assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server._baseurl
    assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_manual_config_with_token(hass):
    """Test creating via manual configuration with only token."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user", "show_advanced_options": True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user_advanced"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"setup_method": MANUAL_SETUP_STRING}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "manual_setup"

    mock_plex_server = MockPlexServer()

    with patch("plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()), patch(
        "plexapi.server.PlexServer", return_value=mock_plex_server
    ), patch("homeassistant.components.plex.PlexWebsocket", autospec=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: MOCK_TOKEN}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == mock_plex_server.friendlyName
    assert result["data"][CONF_SERVER] == mock_plex_server.friendlyName
    assert result["data"][CONF_SERVER_IDENTIFIER] == mock_plex_server.machineIdentifier
    assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server._baseurl
    assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_setup_with_limited_credentials(hass):
    """Test setup with a user with limited permissions."""
    mock_plex_server = MockPlexServer()

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    with patch(
        "plexapi.server.PlexServer", return_value=mock_plex_server
    ), patch.object(
        mock_plex_server, "systemAccounts", side_effect=plexapi.exceptions.Unauthorized
    ) as mock_accounts, patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()
    ), patch(
        "homeassistant.components.plex.PlexWebsocket", autospec=True
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_accounts.called

    plex_server = hass.data[DOMAIN][SERVERS][mock_plex_server.machineIdentifier]
    assert len(plex_server.accounts) == 0
    assert plex_server.owner is None

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED


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
