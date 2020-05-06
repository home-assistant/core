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
    CONF_MONITORED_USERS,
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    CONF_USE_EPISODE_ART,
    DOMAIN,
    MANUAL_SETUP_STRING,
    PLEX_SERVER_CONFIG,
    PLEX_UPDATE_PLATFORMS_SIGNAL,
    SERVERS,
)
from homeassistant.config_entries import ENTRY_STATE_LOADED
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from .const import DEFAULT_DATA, DEFAULT_OPTIONS, MOCK_SERVERS, MOCK_TOKEN
from .mock_classes import MockPlexAccount, MockPlexServer

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_bad_credentials(hass):
    """Test when provided credentials are rejected."""

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


async def test_import_success(hass):
    """Test a successful configuration import."""

    mock_plex_server = MockPlexServer()

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={
                CONF_TOKEN: MOCK_TOKEN,
                CONF_URL: f"https://{MOCK_SERVERS[0][CONF_HOST]}:{MOCK_SERVERS[0][CONF_PORT]}",
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == mock_plex_server.friendlyName
    assert result["data"][CONF_SERVER] == mock_plex_server.friendlyName
    assert result["data"][CONF_SERVER_IDENTIFIER] == mock_plex_server.machineIdentifier
    assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server._baseurl
    assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_import_bad_hostname(hass):
    """Test when an invalid address is provided."""

    with patch(
        "plexapi.server.PlexServer", side_effect=requests.exceptions.ConnectionError
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={
                CONF_TOKEN: MOCK_TOKEN,
                CONF_URL: f"http://{MOCK_SERVERS[0][CONF_HOST]}:{MOCK_SERVERS[0][CONF_PORT]}",
            },
        )
        assert result["type"] == "abort"
        assert result["reason"] == "non-interactive"


async def test_unknown_exception(hass):
    """Test when an unknown exception is encountered."""

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

    await async_setup_component(hass, "http", {"http": {}})

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

    await async_setup_component(hass, "http", {"http": {}})

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

    await async_setup_component(hass, "http", {"http": {}})

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

    await async_setup_component(hass, "http", {"http": {}})

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


async def test_already_configured(hass):
    """Test a duplicated successful flow."""

    mock_plex_server = MockPlexServer()

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERVER: MOCK_SERVERS[0][CONF_SERVER],
            CONF_SERVER_IDENTIFIER: MOCK_SERVERS[0][CONF_SERVER_IDENTIFIER],
        },
        unique_id=MOCK_SERVERS[0][CONF_SERVER_IDENTIFIER],
    ).add_to_hass(hass)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexauth.PlexAuth.initiate_auth"
    ), patch("plexauth.PlexAuth.token", return_value=MOCK_TOKEN):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={
                CONF_TOKEN: MOCK_TOKEN,
                CONF_URL: f"http://{MOCK_SERVERS[0][CONF_HOST]}:{MOCK_SERVERS[0][CONF_PORT]}",
            },
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_all_available_servers_configured(hass):
    """Test when all available servers are already configured."""

    await async_setup_component(hass, "http", {"http": {}})

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
        "homeassistant.components.plex.PlexWebsocket.listen"
    ) as mock_listen:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert mock_listen.called

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
        "homeassistant.components.plex.PlexWebsocket.listen"
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    server_id = mock_plex_server.machineIdentifier

    async_dispatcher_send(hass, PLEX_UPDATE_PLATFORMS_SIGNAL.format(server_id))
    await hass.async_block_till_done()

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

    await async_setup_component(hass, "http", {"http": {}})

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

    await async_setup_component(hass, "http", {"http": {}})

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


async def test_multiple_servers_with_import(hass):
    """Test importing a config with multiple servers available."""

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=2)
    ), patch("plexauth.PlexAuth.initiate_auth"), patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data={CONF_TOKEN: MOCK_TOKEN},
        )
        assert result["type"] == "abort"
        assert result["reason"] == "non-interactive"


async def test_manual_config(hass):
    """Test creating via manual configuration."""

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

    assert result["data_schema"] is None
    hass.config_entries.flow.async_abort(result["flow_id"])

    # Advanced automatic
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user", "show_advanced_options": True}
    )

    assert result["data_schema"] is not None
    assert result["type"] == "form"
    assert result["step_id"] == "user_advanced"

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
        "homeassistant.components.plex.PlexWebsocket.listen"
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
    ), patch("homeassistant.components.plex.PlexWebsocket.listen"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: MOCK_TOKEN}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == mock_plex_server.friendlyName
    assert result["data"][CONF_SERVER] == mock_plex_server.friendlyName
    assert result["data"][CONF_SERVER_IDENTIFIER] == mock_plex_server.machineIdentifier
    assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_plex_server._baseurl
    assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN
