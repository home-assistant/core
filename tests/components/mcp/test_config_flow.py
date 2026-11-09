"""Test the Model Context Protocol config flow."""

import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx2
from mcp import MCPError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
import respx

from homeassistant import config_entries
from homeassistant.components.mcp.auth import AuthenticateHeader
from homeassistant.components.mcp.const import (
    CONF_AUTHORIZATION_URL,
    CONF_SCOPE,
    CONF_SLUG,
    CONF_TOKEN_URL,
    DOMAIN,
)
from homeassistant.const import CONF_API_TOKEN, CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .conftest import (
    AUTH_DOMAIN,
    CLIENT_ID,
    MCP_SERVER_URL,
    OAUTH_AUTHORIZE_URL,
    OAUTH_TOKEN_URL,
    TEST_API_NAME,
)

MCP_SERVER_BASE_URL = "http://1.1.1.1:8080"
OAUTH_DISCOVERY_ENDPOINT = (
    f"{MCP_SERVER_BASE_URL}/.well-known/oauth-authorization-server/mcp"
)
AUTHORIZATION_SERVER = "https://example-auth-server.com"
OAUTH_AUTHORIZATION_SERVER_DISCOVERY_ENDPOINT = (
    f"{AUTHORIZATION_SERVER}/.well-known/oauth-authorization-server"
)
SCOPES_SUPPORTED = ["profile", "email", "phone"]
OAUTH_PROTECTED_RESOURCE_METADATA_RESPONSE = httpx2.Response(
    status_code=200,
    json={
        "resource": MCP_SERVER_URL,
        "authorization_servers": [
            AUTHORIZATION_SERVER,
        ],
        "scopes_supported": SCOPES_SUPPORTED,
        "bearer_methods_supported": ["header"],
    },
)
OAUTH_SERVER_METADATA_RESPONSE = httpx2.Response(
    status_code=200,
    text=json.dumps(
        {
            "authorization_endpoint": OAUTH_AUTHORIZE_URL,
            "token_endpoint": OAUTH_TOKEN_URL,
            "scopes_supported": ["read", "write"],
        }
    ),
)
SCOPES = ["read", "write"]
CALLBACK_PATH = "/auth/external/callback"
OAUTH_CALLBACK_URL = f"https://example.com{CALLBACK_PATH}"
OAUTH_CODE = "abcd"
ADDON_NAME = "Example MCP Server"
ADDON_DISCOVERY_INFO = HassioServiceInfo(
    config={"addon": ADDON_NAME, CONF_URL: MCP_SERVER_URL},
    name=ADDON_NAME,
    slug="example_mcp_server",
    uuid="1234",
)
ADDON_TOKEN = "test-addon-token"
ADDON_DISCOVERY_INFO_WITH_TOKEN = HassioServiceInfo(
    config={"addon": ADDON_NAME, CONF_URL: MCP_SERVER_URL, CONF_TOKEN: ADDON_TOKEN},
    name=ADDON_NAME,
    slug="example_mcp_server",
    uuid="1234",
)
OAUTH_TOKEN_PAYLOAD = {
    "refresh_token": "mock-refresh-token",
    "access_token": "mock-access-token",
    "type": "Bearer",
    "expires_in": 60,
    "scope": " ".join(SCOPES),
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
    response.server_info.name = TEST_API_NAME
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
    mock_mcp_client.return_value.initialize.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (httpx2.TimeoutException("Some timeout"), "timeout_connect"),
        (
            httpx2.HTTPStatusError("", request=None, response=httpx2.Response(500)),
            "cannot_connect",
        ),
        (httpx2.HTTPError("Some HTTP error"), "cannot_connect"),
        (MCPError(-32603, "Internal error"), "cannot_connect"),
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
    response.server_info.name = TEST_API_NAME
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
    response.server_info.name = TEST_API_NAME
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_unique_url(hass: HomeAssistant, mock_mcp_client: Mock) -> None:
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
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_server_missing_capbilities(
    hass: HomeAssistant, mock_mcp_client: Mock
) -> None:
    """Test we handle different client library errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    response = Mock()
    response.server_info.name = TEST_API_NAME
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
@pytest.mark.usefixtures("mock_setup_entry")
async def test_oauth_discovery_flow_without_credentials(
    hass: HomeAssistant, mock_mcp_client: Mock
) -> None:
    """Test OAuth discoveryflow when user has no credentials yet."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # MCP Server returns 401 indicating the client needs to authenticate
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
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

    # The config flow will abort and the user will be taken to the
    # application credentials UI to enter their credentials.
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


async def perform_oauth_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    result: config_entries.ConfigFlowResult,
    authorize_url: str = OAUTH_AUTHORIZE_URL,
    token_url: str = OAUTH_TOKEN_URL,
    scopes: list[str] | None = None,
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
    scope_param = ""
    if scopes:
        scope_param = "&scope=" + "+".join(scopes)
    assert result["url"] == (
        f"{authorize_url}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={OAUTH_CALLBACK_URL}"
        f"&state={state}"
        # Asked for so the server hands back a refresh token
        f"&access_type=offline&prompt=consent{scope_param}"
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
    (
        "oauth_server_metadata_response",
        "expected_authorize_url",
        "expected_token_url",
        "scopes",
    ),
    [
        (OAUTH_SERVER_METADATA_RESPONSE, OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL, SCOPES),
        (
            httpx2.Response(
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
            None,
        ),
        (
            httpx2.Response(status_code=404),
            f"{MCP_SERVER_BASE_URL}/authorize",
            f"{MCP_SERVER_BASE_URL}/token",
            None,
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
    oauth_server_metadata_response: httpx2.Response,
    expected_authorize_url: str,
    expected_token_url: str,
    scopes: list[str] | None,
) -> None:
    """Test for an OAuth authentication flow for an MCP server."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # MCP Server returns 401 indicating the client needs to authenticate
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
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
        scopes=scopes,
    )

    # Client now accepts credentials
    mock_mcp_client.side_effect = None
    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["result"].unique_id is None
    data = result["data"]
    token = data.pop(CONF_TOKEN)
    assert data == {
        "auth_implementation": AUTH_DOMAIN,
        CONF_URL: MCP_SERVER_URL,
        CONF_AUTHORIZATION_URL: expected_authorize_url,
        CONF_TOKEN_URL: expected_token_url,
        CONF_SCOPE: scopes,
    }
    assert token
    token.pop("expires_at")
    assert token == OAUTH_TOKEN_PAYLOAD

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
@pytest.mark.parametrize(
    ("authenticate_header", "resource_metadata_url", "expected_scopes"),
    [
        (
            'Bearer error="invalid_token", resource_metadata="https://example.com/custom-discovery"',
            "https://example.com/custom-discovery",
            SCOPES_SUPPORTED,
        ),
        (
            'Bearer error="invalid_token", resource_metadata="/custom-discovery"',
            f"{MCP_SERVER_BASE_URL}/custom-discovery",
            SCOPES_SUPPORTED,
        ),
        (
            'Bearer error="invalid_token",'
            ' resource_metadata="https://example.com/custom-discovery"'
            ' scope="read write"',
            "https://example.com/custom-discovery",
            ["read", "write"],
        ),
    ],
    ids=[
        "absolute_url",
        "relative_url",
        "with_scopes",
    ],
)
async def test_authentication_discovery_via_header(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    authenticate_header: str,
    resource_metadata_url: str,
    expected_scopes: list[str],
) -> None:
    """Test for an OAuth discovery flow using the WWW-Authenticate header."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # MCP Server returns 401 when first trying to connect via config
    # flow validate_input. The response value has a WWW-Authenticate
    # header with a full URL for the resource metadata.
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required",
        request=None,
        response=httpx2.Response(
            401,
            headers={
                "WWW-Authenticate": authenticate_header,
            },
        ),
    )

    # Discovery process starts. It hits the custom discovery URL directly.
    respx.get(resource_metadata_url).mock(
        return_value=OAUTH_PROTECTED_RESOURCE_METADATA_RESPONSE
    )
    respx.get(OAUTH_AUTHORIZATION_SERVER_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    # Should proceed to credentials choice
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
        authorize_url=OAUTH_AUTHORIZE_URL,
        token_url=OAUTH_TOKEN_URL,
        scopes=expected_scopes,
    )

    # Client now accepts credentials
    mock_mcp_client.side_effect = None
    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    data = result["data"]
    token = data.pop(CONF_TOKEN)
    assert data == {
        "auth_implementation": AUTH_DOMAIN,
        CONF_URL: MCP_SERVER_URL,
        CONF_AUTHORIZATION_URL: OAUTH_AUTHORIZE_URL,
        CONF_TOKEN_URL: OAUTH_TOKEN_URL,
        CONF_SCOPE: expected_scopes,
    }
    assert token
    token.pop("expires_at")
    assert token == OAUTH_TOKEN_PAYLOAD

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
@pytest.mark.parametrize(
    ("resource_metadata"),
    [
        {
            "authorization_servers": [
                AUTHORIZATION_SERVER,
            ],
            "scopes_supported": SCOPES_SUPPORTED,
            "bearer_methods_supported": ["header"],
        },
        {
            "resource": "https://different-resource.com",
            "authorization_servers": [
                AUTHORIZATION_SERVER,
            ],
            "scopes_supported": SCOPES_SUPPORTED,
            "bearer_methods_supported": ["header"],
        },
        {
            "resource": MCP_SERVER_URL,
            "scopes_supported": SCOPES_SUPPORTED,
            "bearer_methods_supported": ["header"],
        },
    ],
    ids=[
        "missing_resource",
        "mismatched_resource",
        "no_authorization_servers",
    ],
)
async def test_invalid_protected_resource_metadata(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    resource_metadata: dict[str, Any],
) -> None:
    """Test for an OAuth discovery flow using the WWW-Authenticate header."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # MCP Server returns 401 when first trying to connect via config
    # flow validate_input. The response value has a WWW-Authenticate
    # header with a full URL for the resource metadata.
    resource_metadata_url = "https://example.com/custom-discovery"
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required",
        request=None,
        response=httpx2.Response(
            401,
            headers={
                "WWW-Authenticate": (
                    'Bearer error="invalid_token",'
                    f' resource_metadata="{resource_metadata_url}"'
                ),
            },
        ),
    )

    # Discovery process starts. It hits the custom discovery URL directly.
    respx.get(resource_metadata_url).mock(
        return_value=httpx2.Response(
            status_code=200,
            json=resource_metadata,
        )
    )
    respx.get(OAUTH_AUTHORIZATION_SERVER_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: MCP_SERVER_URL,
        },
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "cannot_connect"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (httpx2.TimeoutException("Some timeout"), "timeout_connect"),
        (
            httpx2.HTTPStatusError("", request=None, response=httpx2.Response(500)),
            "cannot_connect",
        ),
        (httpx2.HTTPError("Some HTTP error"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_oauth_discovery_failure(
    hass: HomeAssistant,
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
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
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
        (httpx2.TimeoutException("Some timeout"), "timeout_connect"),
        (
            httpx2.HTTPStatusError("", request=None, response=httpx2.Response(500)),
            "cannot_connect",
        ),
        (httpx2.HTTPError("Some HTTP error"), "cannot_connect"),
        (MCPError(-32603, "Internal error"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_authentication_flow_server_failure_abort(
    hass: HomeAssistant,
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
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
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
        scopes=SCOPES,
    )

    # Client fails with an error
    mock_mcp_client.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_error


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_authentication_flow_server_missing_tool_capabilities(
    hass: HomeAssistant,
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
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
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
        scopes=SCOPES,
    )

    # Client can now authenticate
    mock_mcp_client.side_effect = None

    response = Mock()
    response.server_info.name = TEST_API_NAME
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

    result = await perform_oauth_flow(
        hass, aioclient_mock, hass_client_no_auth, result, scopes=SCOPES
    )

    # Verify we can connect to the server
    response = Mock()
    response.server_info.name = TEST_API_NAME
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
        CONF_SCOPE: ["read", "write"],
    }
    assert token
    token.pop("expires_at")
    assert token == OAUTH_TOKEN_PAYLOAD

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
async def test_reauth_flow_upgrade_to_oauth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test reauth flow upgrading a no-auth entry to OAuth."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: MCP_SERVER_URL},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    auth_header = AuthenticateHeader(
        resource_metadata_url="https://example.com/custom-discovery",
        scopes=SCOPES_SUPPORTED,
    )

    # Start reauth flow passing auth_header
    config_entry.async_start_reauth(hass, data={"auth_header": auth_header})
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"

    # Mock discovery URLs (bypassing connection validation)
    respx.get("https://example.com/custom-discovery").mock(
        return_value=OAUTH_PROTECTED_RESOURCE_METADATA_RESPONSE
    )
    respx.get(OAUTH_AUTHORIZATION_SERVER_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    # Click Submit on reauth_confirm
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Flow should proceed to credentials choice
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
        authorize_url=OAUTH_AUTHORIZE_URL,
        token_url=OAUTH_TOKEN_URL,
        scopes=SCOPES_SUPPORTED,
    )

    # Verify we can connect to the server now with the token
    response = Mock()
    response.server_info.name = TEST_API_NAME
    # Return success for validation in async_oauth_create_entry
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.unique_id is None
    assert config_entry.title == TEST_API_NAME
    data = {**config_entry.data}
    token = data.pop(CONF_TOKEN)
    assert data == {
        "auth_implementation": AUTH_DOMAIN,
        CONF_URL: MCP_SERVER_URL,
        CONF_AUTHORIZATION_URL: OAUTH_AUTHORIZE_URL,
        CONF_TOKEN_URL: OAUTH_TOKEN_URL,
        CONF_SCOPE: SCOPES_SUPPORTED,
    }
    assert token
    token.pop("expires_at")
    assert token == OAUTH_TOKEN_PAYLOAD

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
async def test_reauth_flow_upgrade_to_oauth_no_auth_header(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test reauth flow upgrading a no-auth entry to OAuth when no auth header is passed (fallback)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: MCP_SERVER_URL},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    # Start reauth flow without passing auth_header
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"

    # Mock discovery on the default server URL (since there is no auth_header)
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    # Click Submit on reauth_confirm
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Flow should proceed directly to credentials choice menu (without validate_input)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "credentials_choice"


@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
async def test_reauth_flow_missing_implementation(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test reauth recovers when the stored implementation was removed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "removed",
            CONF_URL: MCP_SERVER_URL,
            CONF_AUTHORIZATION_URL: OAUTH_AUTHORIZE_URL,
            CONF_TOKEN_URL: OAUTH_TOKEN_URL,
        },
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"

    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Instead of erroring out, the user can pick or create credentials again
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "credentials_choice"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "pick_implementation"},
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    result = await perform_oauth_flow(
        hass,
        aioclient_mock,
        hass_client_no_auth,
        result,
        authorize_url=OAUTH_AUTHORIZE_URL,
        token_url=OAUTH_TOKEN_URL,
        scopes=SCOPES,
    )

    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    # The entry now points at an implementation that exists again
    assert config_entry.data["auth_implementation"] == AUTH_DOMAIN
    assert config_entry.data[CONF_TOKEN]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("discovery_info", "expected_data", "expected_authorization"),
    [
        pytest.param(
            ADDON_DISCOVERY_INFO,
            {CONF_URL: MCP_SERVER_URL, CONF_SLUG: ADDON_DISCOVERY_INFO.slug},
            None,
            id="no_token",
        ),
        pytest.param(
            ADDON_DISCOVERY_INFO_WITH_TOKEN,
            {
                CONF_URL: MCP_SERVER_URL,
                CONF_API_TOKEN: ADDON_TOKEN,
                CONF_SLUG: ADDON_DISCOVERY_INFO.slug,
            },
            f"Bearer {ADDON_TOKEN}",
            id="token",
        ),
    ],
)
async def test_hassio_discovery_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    mock_http_streamable_client: Mock,
    discovery_info: HassioServiceInfo,
    expected_data: dict[str, str],
    expected_authorization: str | None,
) -> None:
    """Test the discovery flow for an MCP server provided by an app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": ADDON_NAME}
    flows = hass.config_entries.flow.async_progress()
    assert flows[0]["context"]["title_placeholders"] == {"name": ADDON_NAME}

    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["data"] == expected_data
    http_client = mock_http_streamable_client.call_args.kwargs["http_client"]
    assert http_client.headers.get("Authorization") == expected_authorization
    # The discovery uuid lets Supervisor remove the entry with the app
    assert result["result"]
    assert result["result"].unique_id == ADDON_DISCOVERY_INFO.uuid
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({}, id="missing_url"),
        pytest.param({CONF_URL: "not a url"}, id="invalid_url"),
        pytest.param({CONF_URL: "http://[::1/mcp"}, id="unparsable_url"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_invalid_url(
    hass: HomeAssistant, config: dict[str, Any]
) -> None:
    """Test an app that sends discovery info without a usable URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=HassioServiceInfo(
            config=config,
            name=ADDON_NAME,
            slug="example_mcp_server",
            uuid="1234",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


@pytest.mark.parametrize(
    ("entry_data", "discovery_info", "expected_data"),
    [
        pytest.param(
            {CONF_URL: "http://1.1.1.1:9999/mcp"},
            ADDON_DISCOVERY_INFO,
            {CONF_URL: MCP_SERVER_URL},
            id="app_moved",
        ),
        pytest.param(
            {CONF_URL: MCP_SERVER_URL},
            ADDON_DISCOVERY_INFO,
            {CONF_URL: MCP_SERVER_URL},
            id="app_restarted",
        ),
        pytest.param(
            {CONF_URL: MCP_SERVER_URL},
            ADDON_DISCOVERY_INFO_WITH_TOKEN,
            {CONF_URL: MCP_SERVER_URL, CONF_API_TOKEN: ADDON_TOKEN},
            id="token_added",
        ),
        pytest.param(
            {CONF_URL: MCP_SERVER_URL, CONF_API_TOKEN: "old-token"},
            ADDON_DISCOVERY_INFO_WITH_TOKEN,
            {CONF_URL: MCP_SERVER_URL, CONF_API_TOKEN: ADDON_TOKEN},
            id="token_changed",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_updates_entry(
    hass: HomeAssistant,
    entry_data: dict[str, str],
    discovery_info: HassioServiceInfo,
    expected_data: dict[str, str],
) -> None:
    """Test discovery of an already configured app keeps its entry up to date."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDON_DISCOVERY_INFO.uuid,
        data=entry_data,
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data == expected_data


@pytest.mark.parametrize(
    "unique_id",
    [
        pytest.param(ADDON_DISCOVERY_INFO.uuid, id="same_uuid"),
        pytest.param("old-uuid", id="new_uuid"),
    ],
)
@pytest.mark.parametrize(
    "state",
    [
        config_entries.ConfigEntryState.LOADED,
        config_entries.ConfigEntryState.SETUP_RETRY,
        config_entries.ConfigEntryState.SETUP_ERROR,
        config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    ],
)
async def test_hassio_discovery_new_token_reloads_entry(
    hass: HomeAssistant, state: config_entries.ConfigEntryState, unique_id: str
) -> None:
    """Test a new token from the app reloads the entry so it gets used."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_HASSIO,
        unique_id=unique_id,
        data={
            CONF_URL: MCP_SERVER_URL,
            CONF_API_TOKEN: "old-token",
            CONF_SLUG: ADDON_DISCOVERY_INFO.slug,
        },
        title=TEST_API_NAME,
        state=state,
    )
    config_entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_HASSIO},
            data=ADDON_DISCOVERY_INFO_WITH_TOKEN,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.unique_id == ADDON_DISCOVERY_INFO.uuid
    assert config_entry.data[CONF_API_TOKEN] == ADDON_TOKEN
    mock_reload.assert_called_once_with(config_entry.entry_id)


@pytest.mark.parametrize(
    ("entry_data", "discovery_info", "expected_data"),
    [
        pytest.param(
            {
                CONF_URL: "http://1.1.1.1:8080/mcp/secret",
                CONF_API_TOKEN: "old-token",
                CONF_SLUG: ADDON_DISCOVERY_INFO.slug,
            },
            ADDON_DISCOVERY_INFO_WITH_TOKEN,
            {
                CONF_URL: MCP_SERVER_URL,
                CONF_API_TOKEN: ADDON_TOKEN,
                CONF_SLUG: ADDON_DISCOVERY_INFO.slug,
            },
            id="app_moved",
        ),
        pytest.param(
            {CONF_URL: MCP_SERVER_URL, CONF_SLUG: ADDON_DISCOVERY_INFO.slug},
            ADDON_DISCOVERY_INFO,
            {CONF_URL: MCP_SERVER_URL, CONF_SLUG: ADDON_DISCOVERY_INFO.slug},
            id="unchanged",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_new_uuid_updates_entry(
    hass: HomeAssistant,
    entry_data: dict[str, str],
    discovery_info: HassioServiceInfo,
    expected_data: dict[str, str],
) -> None:
    """Test an app that sends its discovery again with a new uuid keeps its entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_HASSIO,
        unique_id="old-uuid",
        data=entry_data,
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.unique_id == ADDON_DISCOVERY_INFO.uuid
    assert config_entry.data == expected_data


@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_other_app(hass: HomeAssistant) -> None:
    """Test discovery of another app leaves the existing app entry alone."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=config_entries.SOURCE_HASSIO,
        unique_id="5678",
        data={CONF_URL: "http://1.1.1.1:9999/mcp", CONF_SLUG: "other_mcp_server"},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert config_entry.unique_id == "5678"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test the discovered MCP server is already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: MCP_SERVER_URL},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        (httpx2.TimeoutException("Some timeout"), "timeout_connect"),
        (
            httpx2.HTTPStatusError("", request=None, response=httpx2.Response(500)),
            "cannot_connect",
        ),
        (httpx2.HTTPError("Some HTTP error"), "cannot_connect"),
        (MCPError(-32603, "Internal error"), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_mcp_client_error(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    side_effect: Exception,
    expected_reason: str,
) -> None:
    """Test the discovered MCP server cannot be reached."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )
    mock_mcp_client.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_missing_capabilities(
    hass: HomeAssistant, mock_mcp_client: Mock
) -> None:
    """Test the discovered MCP server does not support tools."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )
    response = Mock()
    response.server_info.name = TEST_API_NAME
    response.capabilities.tools = None
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_capabilities"


@pytest.mark.parametrize(
    ("discovery_info", "expected_authorization"),
    [
        pytest.param(ADDON_DISCOVERY_INFO, None, id="no_token"),
        pytest.param(
            ADDON_DISCOVERY_INFO_WITH_TOKEN,
            f"Bearer {ADDON_TOKEN}",
            id="token_rejected",
        ),
    ],
)
@respx.mock
@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_requires_authentication(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    mock_http_streamable_client: Mock,
    discovery_info: HassioServiceInfo,
    expected_authorization: str | None,
) -> None:
    """Test the discovered MCP server continues into the OAuth flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=discovery_info,
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    http_client = mock_http_streamable_client.call_args.kwargs["http_client"]
    assert http_client.headers.get("Authorization") == expected_authorization
    # The user is taken to the application credentials UI to enter credentials.
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("current_request_with_host")
@respx.mock
async def test_hassio_discovery_authentication_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    credential: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test an OAuth flow for a discovered MCP server keeps the discovery uuid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "credentials_choice"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "pick_implementation"},
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    result = await perform_oauth_flow(
        hass,
        aioclient_mock,
        hass_client_no_auth,
        result,
        scopes=SCOPES,
    )

    mock_mcp_client.side_effect = None
    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"]
    assert result["result"].unique_id == ADDON_DISCOVERY_INFO.uuid
    assert len(mock_setup_entry.mock_calls) == 1
