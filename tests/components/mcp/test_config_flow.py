"""Test the Model Context Protocol config flow."""

import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import respx

from homeassistant import config_entries
from homeassistant.components.mcp.const import (
    CONF_AUTHORIZATION_URL,
    CONF_TOKEN_URL,
    DOMAIN,
)
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import (
    AUTH_DOMAIN,
    CLIENT_ID,
    MCP_SERVER_URL,
    OAUTH_AUTHORIZE_URL,
    OAUTH_TOKEN_URL,
    TEST_API_NAME,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

MCP_SERVER_BASE_URL = "http://1.1.1.1:8080"
OAUTH_DISCOVERY_ENDPOINT = (
    f"{MCP_SERVER_BASE_URL}/.well-known/oauth-authorization-server"
)
OAUTH_SERVER_METADATA_RESPONSE = httpx.Response(
    status_code=200,
    text=json.dumps(
        {
            "authorization_endpoint": OAUTH_AUTHORIZE_URL,
            "token_endpoint": OAUTH_TOKEN_URL,
        }
    ),
)
CALLBACK_PATH = "/auth/external/callback"
OAUTH_CALLBACK_URL = f"https://example.com{CALLBACK_PATH}"
OAUTH_CODE = "abcd"
OAUTH_TOKEN_PAYLOAD = {
    "refresh_token": "mock-refresh-token",
    "access_token": "mock-access-token",
    "type": "Bearer",
    "expires_in": 60,
}


def encode_state(hass: HomeAssistant, flow_id: str) -> str:
    """Encode the OAuth JWT."""
    return config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": flow_id,
            "redirect_uri": OAUTH_CALLBACK_URL,
        },
    )


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_mcp_client: Mock
) -> None:
    """Test the complete configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["data"] == {
        CONF_URL: MCP_SERVER_URL,
    }
    # Config entry does not have a unique id
    assert result["result"]
    assert result["result"].unique_id is None

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (httpx.TimeoutException("Some timeout"), "timeout_connect"),
        (
            httpx.HTTPStatusError("", request=None, response=httpx.Response(500)),
            "cannot_connect",
        ),
        (httpx.HTTPError("Some HTTP error"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_mcp_client_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle different client library errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Reset the error and make sure the config flow can resume successfully.
    mock_mcp_client.side_effect = None
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["data"] == {
        CONF_URL: MCP_SERVER_URL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "user_input",
    [
        ({CONF_URL: "not a url"}),
        ({CONF_URL: "rtsp://1.1.1.1"}),
    ],
)
async def test_input_form_validation_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    user_input: dict[str, Any],
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}

    # Reset the error and make sure the config flow can resume successfully.
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["data"] == {
        CONF_URL: MCP_SERVER_URL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_unique_url(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_mcp_client: Mock
) -> None:
    """Test that the same url cannot be configured twice."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: MCP_SERVER_URL},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_server_missing_capbilities(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
) -> None:
    """Test we handle different client library errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    response.capabilities.tools = None
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_capabilities"


@respx.mock
async def test_oauth_discovery_flow_without_credentials(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
) -> None:
    """Test for an OAuth discoveryflow for an MCP server where the user has not yet entered credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # MCP Server returns 401 indicating the client needs to authenticate
    mock_mcp_client.side_effect = httpx.HTTPStatusError(
        "Authentication required", request=None, response=httpx.Response(401)
    )
    # Prepare the OAuth Server metadata
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    # The config flow will abort and the user will be taken to the application credentials UI
    # to enter their credentials.
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


async def perform_oauth_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    result: config_entries.ConfigFlowResult,
    authorize_url: str = OAUTH_AUTHORIZE_URL,
    token_url: str = OAUTH_TOKEN_URL,
) -> config_entries.ConfigFlowResult:
    """Perform the common steps of the OAuth flow.

    Expects to be called from the step where the user selects credentials.
    """
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": OAUTH_CALLBACK_URL,
        },
    )
    assert result["url"] == (
        f"{authorize_url}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={OAUTH_CALLBACK_URL}"
        f"&state={state}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"{CALLBACK_PATH}?code={OAUTH_CODE}&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        token_url,
        json=OAUTH_TOKEN_PAYLOAD,
    )

    return result


@pytest.mark.parametrize(
    ("oauth_server_metadata_response", "expected_authorize_url", "expected_token_url"),
    [
        (OAUTH_SERVER_METADATA_RESPONSE, OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL),
        (
            httpx.Response(
                status_code=200,
                text=json.dumps(
                    {
                        "authorization_endpoint": "/authorize-path",
                        "token_endpoint": "/token-path",
                    }
                ),
            ),
            f"{MCP_SERVER_BASE_URL}/authorize-path",
            f"{MCP_SERVER_BASE_URL}/token-path",
        ),
        (
            httpx.Response(status_code=404),
            f"{MCP_SERVER_BASE_URL}/authorize",
            f"{MCP_SERVER_BASE_URL}/token",
        ),
    ],
    ids=(
        "discovery",
        "relative_paths",
        "no_discovery_metadata",
    ),
)
@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
async def test_authentication_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    oauth_server_metadata_response: httpx.Response,
    expected_authorize_url: str,
    expected_token_url: str,
) -> None:
    """Test for an OAuth authentication flow for an MCP server."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # MCP Server returns 401 indicating the client needs to authenticate
    mock_mcp_client.side_effect = httpx.HTTPStatusError(
        "Authentication required", request=None, response=httpx.Response(401)
    )
    # Prepare the OAuth Server metadata
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=oauth_server_metadata_response
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "credentials_choice"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "next_step_id": "pick_implementation",
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    result = await perform_oauth_flow(
        hass,
        aioclient_mock,
        hass_client_no_auth,
        result,
        authorize_url=expected_authorize_url,
        token_url=expected_token_url,
    )

    # Client now accepts credentials
    mock_mcp_client.side_effect = None
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    data = result["data"]
    token = data.pop(CONF_TOKEN)
    assert data == {
        "auth_implementation": AUTH_DOMAIN,
        CONF_URL: MCP_SERVER_URL,
        CONF_AUTHORIZATION_URL: expected_authorize_url,
        CONF_TOKEN_URL: expected_token_url,
    }
    assert token
    token.pop("expires_at")
    assert token == OAUTH_TOKEN_PAYLOAD

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (httpx.TimeoutException("Some timeout"), "timeout_connect"),
        (
            httpx.HTTPStatusError("", request=None, response=httpx.Response(500)),
            "cannot_connect",
        ),
        (httpx.HTTPError("Some HTTP error"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
async def test_oauth_discovery_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test for an OAuth authentication flow for an MCP server."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # MCP Server returns 401 indicating the client needs to authenticate
    mock_mcp_client.side_effect = httpx.HTTPStatusError(
        "Authentication required", request=None, response=httpx.Response(401)
    )
    # Prepare the OAuth Server metadata
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(side_effect=side_effect)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (httpx.TimeoutException("Some timeout"), "timeout_connect"),
        (
            httpx.HTTPStatusError("", request=None, response=httpx.Response(500)),
            "cannot_connect",
        ),
        (httpx.HTTPError("Some HTTP error"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
async def test_authentication_flow_server_failure_abort(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test for an OAuth authentication flow for an MCP server."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # MCP Server returns 401 indicating the client needs to authenticate
    mock_mcp_client.side_effect = httpx.HTTPStatusError(
        "Authentication required", request=None, response=httpx.Response(401)
    )
    # Prepare the OAuth Server metadata
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "credentials_choice"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "next_step_id": "pick_implementation",
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    result = await perform_oauth_flow(
        hass,
        aioclient_mock,
        hass_client_no_auth,
        result,
    )

    # Client fails with an error
    mock_mcp_client.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error


@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
async def test_authentication_flow_server_missing_tool_capabilities(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test for an OAuth authentication flow for an MCP server."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # MCP Server returns 401 indicating the client needs to authenticate
    mock_mcp_client.side_effect = httpx.HTTPStatusError(
        "Authentication required", request=None, response=httpx.Response(401)
    )
    # Prepare the OAuth Server metadata
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "credentials_choice"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "next_step_id": "pick_implementation",
        },
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    result = await perform_oauth_flow(
        hass,
        aioclient_mock,
        hass_client_no_auth,
        result,
    )

    # Client can now authenticate
    mock_mcp_client.side_effect = None

    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    response.capabilities.tools = None
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_capabilities"


@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    config_entry_with_auth: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test for an OAuth authentication flow for an MCP server."""
    config_entry_with_auth.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result = await perform_oauth_flow(hass, aioclient_mock, hass_client_no_auth, result)

    # Verify we can connect to the server
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry_with_auth.unique_id == AUTH_DOMAIN
    assert config_entry_with_auth.title == TEST_API_NAME
    data = {**config_entry_with_auth.data}
    token = data.pop(CONF_TOKEN)
    assert data == {
        "auth_implementation": AUTH_DOMAIN,
        CONF_URL: MCP_SERVER_URL,
        CONF_AUTHORIZATION_URL: OAUTH_AUTHORIZE_URL,
        CONF_TOKEN_URL: OAUTH_TOKEN_URL,
    }
    assert token
    token.pop("expires_at")
    assert token == OAUTH_TOKEN_PAYLOAD

    assert len(mock_setup_entry.mock_calls) == 1
