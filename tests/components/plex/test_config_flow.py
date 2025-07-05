"""Tests for Plex config flow."""

import copy
from http import HTTPStatus
import ssl
from unittest.mock import AsyncMock, patch

import plexapi.exceptions
import pytest
import requests.exceptions
import requests_mock

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
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import DEFAULT_OPTIONS, MOCK_SERVERS, MOCK_TOKEN, PLEX_DIRECT_URL
from .mock_classes import MockGDM

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_bad_credentials(hass: HomeAssistant) -> None:
    """Test when provided credentials are rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "plexapi.myplex.MyPlexAccount", side_effect=plexapi.exceptions.Unauthorized
        ),
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value="BAD TOKEN"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"][CONF_TOKEN] == "faulty_credentials"


@pytest.mark.usefixtures("current_request_with_host")
async def test_bad_hostname(hass: HomeAssistant, mock_plex_calls) -> None:
    """Test when an invalid address is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "plexapi.myplex.MyPlexResource.connect",
            side_effect=requests.exceptions.ConnectionError,
        ),
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=MOCK_TOKEN),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"][CONF_HOST] == "not_found"


@pytest.mark.usefixtures("current_request_with_host")
async def test_unknown_exception(hass: HomeAssistant) -> None:
    """Test when an unknown exception is encountered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("plexapi.myplex.MyPlexAccount", side_effect=Exception),
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value="MOCK_TOKEN"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_servers_found(
    hass: HomeAssistant,
    mock_plex_calls,
    requests_mock: requests_mock.Mocker,
    empty_payload,
) -> None:
    """Test when no servers are on an account."""
    requests_mock.get("https://plex.tv/api/v2/resources", text=empty_payload)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=MOCK_TOKEN),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "no_servers"


@pytest.mark.usefixtures("current_request_with_host")
async def test_single_available_server(
    hass: HomeAssistant,
    mock_plex_calls,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test creating an entry with one server available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=MOCK_TOKEN),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.CREATE_ENTRY

        assert (
            result["title"] == "https://1-2-3-4.123456789001234567890.plex.direct:32400"
        )
        assert result["data"][CONF_SERVER] == "Plex Server 1"
        assert result["data"][CONF_SERVER_IDENTIFIER] == "unique_id_123"
        assert (
            result["data"][PLEX_SERVER_CONFIG][CONF_URL]
            == "https://1-2-3-4.123456789001234567890.plex.direct:32400"
        )
        assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN

    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("current_request_with_host")
async def test_multiple_servers_with_selection(
    hass: HomeAssistant,
    mock_plex_calls,
    requests_mock: requests_mock.Mocker,
    plextv_resources_two_servers,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test creating an entry with multiple servers available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    requests_mock.get(
        "https://plex.tv/api/v2/resources",
        text=plextv_resources_two_servers,
    )
    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=MOCK_TOKEN),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_server"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SERVER_IDENTIFIER: MOCK_SERVERS[0][CONF_SERVER_IDENTIFIER]
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

        assert (
            result["title"] == "https://1-2-3-4.123456789001234567890.plex.direct:32400"
        )
        assert result["data"][CONF_SERVER] == "Plex Server 1"
        assert result["data"][CONF_SERVER_IDENTIFIER] == "unique_id_123"
        assert (
            result["data"][PLEX_SERVER_CONFIG][CONF_URL]
            == "https://1-2-3-4.123456789001234567890.plex.direct:32400"
        )
        assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN

    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("current_request_with_host")
async def test_adding_last_unconfigured_server(
    hass: HomeAssistant,
    mock_plex_calls,
    requests_mock: requests_mock.Mocker,
    plextv_resources_two_servers,
    mock_setup_entry: AsyncMock,
) -> None:
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    requests_mock.get(
        "https://plex.tv/api/v2/resources",
        text=plextv_resources_two_servers,
    )

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=MOCK_TOKEN),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.CREATE_ENTRY

        assert (
            result["title"] == "https://1-2-3-4.123456789001234567890.plex.direct:32400"
        )
        assert result["data"][CONF_SERVER] == "Plex Server 1"
        assert result["data"][CONF_SERVER_IDENTIFIER] == "unique_id_123"
        assert (
            result["data"][PLEX_SERVER_CONFIG][CONF_URL]
            == "https://1-2-3-4.123456789001234567890.plex.direct:32400"
        )
        assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN

    assert mock_setup_entry.call_count == 2


@pytest.mark.usefixtures("current_request_with_host")
async def test_all_available_servers_configured(
    hass: HomeAssistant,
    entry,
    requests_mock: requests_mock.Mocker,
    plextv_account,
    plextv_resources_two_servers,
) -> None:
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    requests_mock.get("https://plex.tv/api/v2/user", text=plextv_account)
    requests_mock.get(
        "https://plex.tv/api/v2/resources",
        text=plextv_resources_two_servers,
    )

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=MOCK_TOKEN),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "all_configured"


async def test_option_flow(hass: HomeAssistant, entry, mock_plex_server) -> None:
    """Test config options flow selection."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "plex_mp_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_EPISODE_ART: True,
            CONF_IGNORE_NEW_SHARED_USERS: True,
            CONF_MONITORED_USERS: list(mock_plex_server.accounts),
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        Platform.MEDIA_PLAYER: {
            CONF_USE_EPISODE_ART: True,
            CONF_IGNORE_NEW_SHARED_USERS: True,
            CONF_MONITORED_USERS: {
                user: {"enabled": True} for user in mock_plex_server.accounts
            },
            CONF_IGNORE_PLEX_WEB_CLIENTS: False,
        }
    }


async def test_missing_option_flow(
    hass: HomeAssistant, entry, mock_plex_server
) -> None:
    """Test config options flow selection when no options stored."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "plex_mp_settings"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_EPISODE_ART: True,
            CONF_IGNORE_NEW_SHARED_USERS: True,
            CONF_MONITORED_USERS: list(mock_plex_server.accounts),
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        Platform.MEDIA_PLAYER: {
            CONF_USE_EPISODE_ART: True,
            CONF_IGNORE_NEW_SHARED_USERS: True,
            CONF_MONITORED_USERS: {
                user: {"enabled": True} for user in mock_plex_server.accounts
            },
            CONF_IGNORE_PLEX_WEB_CLIENTS: False,
        }
    }


async def test_option_flow_new_users_available(
    hass: HomeAssistant, entry, setup_plex_server
) -> None:
    """Test config options multiselect defaults when new Plex users are seen."""
    OPTIONS_OWNER_ONLY = copy.deepcopy(DEFAULT_OPTIONS)
    OPTIONS_OWNER_ONLY[Platform.MEDIA_PLAYER][CONF_MONITORED_USERS] = {
        "User 1": {"enabled": True}
    }
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options=OPTIONS_OWNER_ONLY)

    mock_plex_server = await setup_plex_server(config_entry=entry)
    await hass.async_block_till_done()

    server_id = "unique_id_123"
    monitored_users = hass.data[DOMAIN][SERVERS][server_id].option_monitored_users

    new_users = [x for x in mock_plex_server.accounts if x not in monitored_users]
    assert len(monitored_users) == 1
    assert len(new_users) == 2

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "plex_mp_settings"
    multiselect_defaults = result["data_schema"].schema["monitored_users"].options

    assert "[Owner]" in multiselect_defaults["User 1"]
    for user in new_users:
        assert "[New]" in multiselect_defaults[user]


@pytest.mark.usefixtures("current_request_with_host")
async def test_external_timed_out(hass: HomeAssistant) -> None:
    """Test when external flow times out."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=None),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "token_request_timeout"


@pytest.mark.usefixtures("current_request_with_host")
async def test_callback_view(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test callback view."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=MOCK_TOKEN),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        client = await hass_client_no_auth()
        forward_url = f"{config_flow.AUTH_CALLBACK_PATH}?flow_id={result['flow_id']}"

        resp = await client.get(forward_url)
        assert resp.status == HTTPStatus.OK


@pytest.mark.usefixtures("current_request_with_host")
async def test_manual_config(hass: HomeAssistant, mock_plex_calls) -> None:
    """Test creating via manual configuration."""

    class WrongCertValidaitionException(requests.exceptions.SSLError):
        """Mock the exception showing an unmatched error."""

        def __init__(self) -> None:  # pylint: disable=super-init-not-called
            self.__context__ = ssl.SSLCertVerificationError(
                "some random message that doesn't match"
            )

    # Basic mode
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["data_schema"] is None
    hass.config_entries.flow.async_abort(result["flow_id"])

    # Advanced automatic
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    assert result["data_schema"] is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_advanced"

    with patch("plexauth.PlexAuth.initiate_auth"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"setup_method": AUTOMATIC_SETUP_STRING}
        )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    hass.config_entries.flow.async_abort(result["flow_id"])

    # Advanced manual
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    assert result["data_schema"] is not None
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_advanced"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"setup_method": MANUAL_SETUP_STRING}
    )

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_setup"
    assert result["errors"]["base"] == "host_or_token"

    with patch(
        "plexapi.server.PlexServer",
        side_effect=requests.exceptions.SSLError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_setup"
    assert result["errors"]["base"] == "ssl_error"

    with patch(
        "plexapi.server.PlexServer",
        side_effect=WrongCertValidaitionException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_setup"
    assert result["errors"]["base"] == "ssl_error"

    with patch(
        "homeassistant.components.plex.PlexServer.connect",
        side_effect=requests.exceptions.SSLError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_setup"
    assert result["errors"]["base"] == "ssl_error"

    with (
        patch("homeassistant.components.plex.PlexWebsocket", autospec=True),
        patch("homeassistant.components.plex.GDM", return_value=MockGDM(disabled=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MANUAL_SERVER
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert result["title"] == "http://1.2.3.4:32400"
    assert result["data"][CONF_SERVER] == "Plex Server 1"
    assert result["data"][CONF_SERVER_IDENTIFIER] == "unique_id_123"
    assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == "http://1.2.3.4:32400"
    assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN


async def test_manual_config_with_token(
    hass: HomeAssistant,
    mock_plex_calls,
    requests_mock: requests_mock.Mocker,
    empty_library,
    empty_payload,
) -> None:
    """Test creating via manual configuration with only token."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_advanced"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"setup_method": MANUAL_SETUP_STRING}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_setup"

    with (
        patch("homeassistant.components.plex.GDM", return_value=MockGDM(disabled=True)),
        patch("homeassistant.components.plex.PlexWebsocket", autospec=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_TOKEN: MOCK_TOKEN}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    mock_url = "https://1-2-3-4.123456789001234567890.plex.direct:32400"

    assert result["title"] == mock_url
    assert result["data"][CONF_SERVER] == "Plex Server 1"
    assert result["data"][CONF_SERVER_IDENTIFIER] == "unique_id_123"
    assert result["data"][PLEX_SERVER_CONFIG][CONF_URL] == mock_url
    assert result["data"][PLEX_SERVER_CONFIG][CONF_TOKEN] == MOCK_TOKEN

    # Complete Plex integration setup before teardown
    requests_mock.get(f"{mock_url}/library", text=empty_library)
    requests_mock.get(f"{mock_url}/library/sections", text=empty_payload)
    await hass.async_block_till_done()


async def test_integration_discovery(hass: HomeAssistant) -> None:
    """Test integration self-discovery."""
    mock_gdm = MockGDM()

    with patch("homeassistant.components.plex.config_flow.GDM", return_value=mock_gdm):
        await config_flow.async_discover(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

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


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_plex_calls: None,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test setup and reauthorization of a Plex token."""
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    flow_id = result["flow_id"]

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value="BRAND_NEW_TOKEN"),
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert result["flow_id"] == flow_id

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_SERVER] == "Plex Server 1"
    assert entry.data[CONF_SERVER_IDENTIFIER] == "unique_id_123"
    assert entry.data[PLEX_SERVER_CONFIG][CONF_URL] == PLEX_DIRECT_URL
    assert entry.data[PLEX_SERVER_CONFIG][CONF_TOKEN] == "BRAND_NEW_TOKEN"

    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("current_request_with_host")
async def test_reauth_multiple_servers_available(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    mock_plex_calls: None,
    requests_mock: requests_mock.Mocker,
    plextv_resources_two_servers: str,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test setup and reauthorization of a Plex token when multiple servers are available."""
    requests_mock.get(
        "https://plex.tv/api/v2/resources",
        text=plextv_resources_two_servers,
    )

    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    flow_id = result["flow_id"]

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value="BRAND_NEW_TOKEN"),
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, user_input={})
        assert result["type"] is FlowResultType.EXTERNAL_STEP

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.EXTERNAL_STEP_DONE

        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.ABORT
        assert result["flow_id"] == flow_id
        assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_SERVER] == "Plex Server 1"
    assert entry.data[CONF_SERVER_IDENTIFIER] == "unique_id_123"
    assert entry.data[PLEX_SERVER_CONFIG][CONF_URL] == PLEX_DIRECT_URL
    assert entry.data[PLEX_SERVER_CONFIG][CONF_TOKEN] == "BRAND_NEW_TOKEN"

    mock_setup_entry.assert_called_once()


async def test_client_request_missing(hass: HomeAssistant) -> None:
    """Test when client headers are not set properly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=None),
        pytest.raises(RuntimeError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )


@pytest.mark.usefixtures("current_request_with_host")
async def test_client_header_issues(hass: HomeAssistant) -> None:
    """Test when client headers are not set properly."""

    class MockRequest:
        headers = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch("plexauth.PlexAuth.initiate_auth"),
        patch("plexauth.PlexAuth.token", return_value=None),
        patch(
            "homeassistant.helpers.http.current_request.get",
            return_value=MockRequest(),
        ),
        pytest.raises(
            RuntimeError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
