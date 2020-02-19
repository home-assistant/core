"""Tests for Plex config flow."""
import copy
from unittest.mock import patch

import asynctest
import plexapi.exceptions
import requests.exceptions

from homeassistant.components.plex import config_flow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_TOKEN, CONF_URL
from homeassistant.setup import async_setup_component

from .mock_classes import MOCK_SERVERS, MockPlexAccount, MockPlexServer

from tests.common import MockConfigEntry

MOCK_TOKEN = "secret_token"
MOCK_FILE_CONTENTS = {
    f"{MOCK_SERVERS[0][CONF_HOST]}:{MOCK_SERVERS[0][CONF_PORT]}": {
        "ssl": False,
        "token": MOCK_TOKEN,
        "verify": True,
    }
}

DEFAULT_OPTIONS = {
    config_flow.MP_DOMAIN: {
        config_flow.CONF_USE_EPISODE_ART: False,
        config_flow.CONF_SHOW_ALL_CONTROLS: False,
        config_flow.CONF_IGNORE_NEW_SHARED_USERS: False,
    }
}


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.PlexFlowHandler()
    flow.hass = hass
    return flow


async def test_bad_credentials(hass):
    """Test when provided credentials are rejected."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with patch(
        "plexapi.myplex.MyPlexAccount", side_effect=plexapi.exceptions.Unauthorized
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value="BAD TOKEN"
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] == "form"
        assert result["step_id"] == "start_website_auth"
        assert result["errors"]["base"] == "faulty_credentials"


async def test_import_file_from_discovery(hass):
    """Test importing a legacy file during discovery."""

    file_host_and_port, file_config = list(MOCK_FILE_CONTENTS.items())[0]
    file_use_ssl = file_config[CONF_SSL]
    file_prefix = "https" if file_use_ssl else "http"
    used_url = f"{file_prefix}://{file_host_and_port}"

    mock_plex_server = MockPlexServer(ssl=file_use_ssl)

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "homeassistant.components.plex.config_flow.load_json",
        return_value=MOCK_FILE_CONTENTS,
    ):

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "discovery"},
            data={
                CONF_HOST: MOCK_SERVERS[0][CONF_HOST],
                CONF_PORT: MOCK_SERVERS[0][CONF_PORT],
            },
        )
        assert result["type"] == "create_entry"
        assert result["title"] == mock_plex_server.friendlyName
        assert result["data"][config_flow.CONF_SERVER] == mock_plex_server.friendlyName
        assert (
            result["data"][config_flow.CONF_SERVER_IDENTIFIER]
            == mock_plex_server.machineIdentifier
        )
        assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL] == used_url
        assert (
            result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN]
            == file_config[CONF_TOKEN]
        )


async def test_discovery(hass):
    """Test starting a flow from discovery."""
    with patch("homeassistant.components.plex.config_flow.load_json", return_value={}):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "discovery"},
            data={
                CONF_HOST: MOCK_SERVERS[0][CONF_HOST],
                CONF_PORT: MOCK_SERVERS[0][CONF_PORT],
            },
        )
        assert result["type"] == "abort"
        assert result["reason"] == "discovery_no_file"


async def test_discovery_while_in_progress(hass):
    """Test starting a flow from discovery."""

    await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "discovery"},
        data={
            CONF_HOST: MOCK_SERVERS[0][CONF_HOST],
            CONF_PORT: MOCK_SERVERS[0][CONF_PORT],
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_import_success(hass):
    """Test a successful configuration import."""

    mock_plex_server = MockPlexServer()

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "import"},
            data={
                CONF_TOKEN: MOCK_TOKEN,
                CONF_URL: f"https://{MOCK_SERVERS[0][CONF_HOST]}:{MOCK_SERVERS[0][CONF_PORT]}",
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == mock_plex_server.friendlyName
    assert result["data"][config_flow.CONF_SERVER] == mock_plex_server.friendlyName
    assert (
        result["data"][config_flow.CONF_SERVER_IDENTIFIER]
        == mock_plex_server.machineIdentifier
    )
    assert (
        result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL]
        == mock_plex_server.url_in_use
    )
    assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_import_bad_hostname(hass):
    """Test when an invalid address is provided."""

    with patch(
        "plexapi.server.PlexServer", side_effect=requests.exceptions.ConnectionError
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
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
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with patch("plexapi.myplex.MyPlexAccount", side_effect=Exception), asynctest.patch(
        "plexauth.PlexAuth.initiate_auth"
    ), asynctest.patch("plexauth.PlexAuth.token", return_value="MOCK_TOKEN"):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
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
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=0)
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "form"
        assert result["step_id"] == "start_website_auth"
        assert result["errors"]["base"] == "no_servers"


async def test_single_available_server(hass):
    """Test creating an entry with one server available."""

    mock_plex_server = MockPlexServer()

    await async_setup_component(hass, "http", {"http": {}})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with patch("plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount()), patch(
        "plexapi.server.PlexServer", return_value=mock_plex_server
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "create_entry"
        assert result["title"] == mock_plex_server.friendlyName
        assert result["data"][config_flow.CONF_SERVER] == mock_plex_server.friendlyName
        assert (
            result["data"][config_flow.CONF_SERVER_IDENTIFIER]
            == mock_plex_server.machineIdentifier
        )
        assert (
            result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL]
            == mock_plex_server.url_in_use
        )
        assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_multiple_servers_with_selection(hass):
    """Test creating an entry with multiple servers available."""

    mock_plex_server = MockPlexServer()

    await async_setup_component(hass, "http", {"http": {}})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=2)
    ), patch(
        "plexapi.server.PlexServer", return_value=mock_plex_server
    ), asynctest.patch(
        "plexauth.PlexAuth.initiate_auth"
    ), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "form"
        assert result["step_id"] == "select_server"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_SERVER: MOCK_SERVERS[0][config_flow.CONF_SERVER]
            },
        )
        assert result["type"] == "create_entry"
        assert result["title"] == mock_plex_server.friendlyName
        assert result["data"][config_flow.CONF_SERVER] == mock_plex_server.friendlyName
        assert (
            result["data"][config_flow.CONF_SERVER_IDENTIFIER]
            == mock_plex_server.machineIdentifier
        )
        assert (
            result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL]
            == mock_plex_server.url_in_use
        )
        assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_adding_last_unconfigured_server(hass):
    """Test automatically adding last unconfigured server when multiple servers on account."""

    mock_plex_server = MockPlexServer()

    await async_setup_component(hass, "http", {"http": {}})

    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER_IDENTIFIER: MOCK_SERVERS[1][
                config_flow.CONF_SERVER_IDENTIFIER
            ],
            config_flow.CONF_SERVER: MOCK_SERVERS[1][config_flow.CONF_SERVER],
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=2)
    ), patch(
        "plexapi.server.PlexServer", return_value=mock_plex_server
    ), asynctest.patch(
        "plexauth.PlexAuth.initiate_auth"
    ), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "create_entry"
        assert result["title"] == mock_plex_server.friendlyName
        assert result["data"][config_flow.CONF_SERVER] == mock_plex_server.friendlyName
        assert (
            result["data"][config_flow.CONF_SERVER_IDENTIFIER]
            == mock_plex_server.machineIdentifier
        )
        assert (
            result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_URL]
            == mock_plex_server.url_in_use
        )
        assert result["data"][config_flow.PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_already_configured(hass):
    """Test a duplicated successful flow."""

    mock_plex_server = MockPlexServer()

    flow = init_config_flow(hass)
    flow.context = {"source": "import"}
    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER: MOCK_SERVERS[0][config_flow.CONF_SERVER],
            config_flow.CONF_SERVER_IDENTIFIER: MOCK_SERVERS[0][
                config_flow.CONF_SERVER_IDENTIFIER
            ],
        },
    ).add_to_hass(hass)

    with patch(
        "plexapi.server.PlexServer", return_value=mock_plex_server
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await flow.async_step_import(
            {
                CONF_TOKEN: MOCK_TOKEN,
                CONF_URL: f"http://{MOCK_SERVERS[0][CONF_HOST]}:{MOCK_SERVERS[0][CONF_PORT]}",
            }
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_all_available_servers_configured(hass):
    """Test when all available servers are already configured."""

    await async_setup_component(hass, "http", {"http": {}})

    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER_IDENTIFIER: MOCK_SERVERS[0][
                config_flow.CONF_SERVER_IDENTIFIER
            ],
            config_flow.CONF_SERVER: MOCK_SERVERS[0][config_flow.CONF_SERVER],
        },
    ).add_to_hass(hass)

    MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_SERVER_IDENTIFIER: MOCK_SERVERS[1][
                config_flow.CONF_SERVER_IDENTIFIER
            ],
            config_flow.CONF_SERVER: MOCK_SERVERS[1][config_flow.CONF_SERVER],
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=2)
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external_done"

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "abort"
        assert result["reason"] == "all_configured"


async def test_option_flow(hass):
    """Test config options flow selection."""

    mock_plex_server = MockPlexServer(load_users=False)

    MOCK_SERVER_ID = MOCK_SERVERS[0][config_flow.CONF_SERVER_IDENTIFIER]
    hass.data[config_flow.DOMAIN] = {
        config_flow.SERVERS: {MOCK_SERVER_ID: mock_plex_server}
    }

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={config_flow.CONF_SERVER_IDENTIFIER: MOCK_SERVER_ID},
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == "form"
    assert result["step_id"] == "plex_mp_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            config_flow.CONF_USE_EPISODE_ART: True,
            config_flow.CONF_SHOW_ALL_CONTROLS: True,
            config_flow.CONF_IGNORE_NEW_SHARED_USERS: True,
            config_flow.CONF_MONITORED_USERS: list(mock_plex_server.accounts),
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        config_flow.MP_DOMAIN: {
            config_flow.CONF_USE_EPISODE_ART: True,
            config_flow.CONF_SHOW_ALL_CONTROLS: True,
            config_flow.CONF_IGNORE_NEW_SHARED_USERS: True,
            config_flow.CONF_MONITORED_USERS: {
                user: {"enabled": True} for user in mock_plex_server.accounts
            },
        }
    }


async def test_option_flow_loading_saved_users(hass):
    """Test config options flow selection when loading existing user config."""

    mock_plex_server = MockPlexServer(load_users=True)

    MOCK_SERVER_ID = MOCK_SERVERS[0][config_flow.CONF_SERVER_IDENTIFIER]
    hass.data[config_flow.DOMAIN] = {
        config_flow.SERVERS: {MOCK_SERVER_ID: mock_plex_server}
    }

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={config_flow.CONF_SERVER_IDENTIFIER: MOCK_SERVER_ID},
        options=DEFAULT_OPTIONS,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == "form"
    assert result["step_id"] == "plex_mp_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            config_flow.CONF_USE_EPISODE_ART: True,
            config_flow.CONF_SHOW_ALL_CONTROLS: True,
            config_flow.CONF_IGNORE_NEW_SHARED_USERS: True,
            config_flow.CONF_MONITORED_USERS: list(mock_plex_server.accounts),
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        config_flow.MP_DOMAIN: {
            config_flow.CONF_USE_EPISODE_ART: True,
            config_flow.CONF_SHOW_ALL_CONTROLS: True,
            config_flow.CONF_IGNORE_NEW_SHARED_USERS: True,
            config_flow.CONF_MONITORED_USERS: {
                user: {"enabled": True} for user in mock_plex_server.accounts
            },
        }
    }


async def test_option_flow_new_users_available(hass):
    """Test config options flow selection when new Plex accounts available."""

    mock_plex_server = MockPlexServer(load_users=True, num_users=2)

    MOCK_SERVER_ID = MOCK_SERVERS[0][config_flow.CONF_SERVER_IDENTIFIER]
    hass.data[config_flow.DOMAIN] = {
        config_flow.SERVERS: {MOCK_SERVER_ID: mock_plex_server}
    }

    OPTIONS_WITH_USERS = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_WITH_USERS[config_flow.MP_DOMAIN][config_flow.CONF_MONITORED_USERS] = {
        "a": {"enabled": True}
    }

    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={config_flow.CONF_SERVER_IDENTIFIER: MOCK_SERVER_ID},
        options=OPTIONS_WITH_USERS,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == "form"
    assert result["step_id"] == "plex_mp_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            config_flow.CONF_USE_EPISODE_ART: True,
            config_flow.CONF_SHOW_ALL_CONTROLS: True,
            config_flow.CONF_IGNORE_NEW_SHARED_USERS: True,
            config_flow.CONF_MONITORED_USERS: list(mock_plex_server.accounts),
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        config_flow.MP_DOMAIN: {
            config_flow.CONF_USE_EPISODE_ART: True,
            config_flow.CONF_SHOW_ALL_CONTROLS: True,
            config_flow.CONF_IGNORE_NEW_SHARED_USERS: True,
            config_flow.CONF_MONITORED_USERS: {
                user: {"enabled": True} for user in mock_plex_server.accounts
            },
        }
    }


async def test_external_timed_out(hass):
    """Test when external flow times out."""

    await async_setup_component(hass, "http", {"http": {}})

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=None
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
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
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "start_website_auth"

    with asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] == "external"

        client = await aiohttp_client(hass.http.app)
        forward_url = f'{config_flow.AUTH_CALLBACK_PATH}?flow_id={result["flow_id"]}'

        resp = await client.get(forward_url)
        assert resp.status == 200


async def test_multiple_servers_with_import(hass):
    """Test importing a config with multiple servers available."""

    with patch(
        "plexapi.myplex.MyPlexAccount", return_value=MockPlexAccount(servers=2)
    ), asynctest.patch("plexauth.PlexAuth.initiate_auth"), asynctest.patch(
        "plexauth.PlexAuth.token", return_value=MOCK_TOKEN
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": "import"},
            data={CONF_TOKEN: MOCK_TOKEN},
        )
        assert result["type"] == "abort"
        assert result["reason"] == "non-interactive"
