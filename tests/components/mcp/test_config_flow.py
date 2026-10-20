"""Test the Model Context Protocol config flow."""

import datetime as dt
from http import HTTPStatus
import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx2
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from pytest_homeassistant.typing import ClientSessionGenerator
import respx
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.mcp.auth import AuthenticateHeader
from homeassistant.components.mcp.const import (
    CONF_AUTHORIZATION_URL,
    CONF_SCOPE,
    CONF_SLUG,
    CONF_TOKEN_URL,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.util import dt as dt_util

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


async def test_hassio_discovery_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_mcp_client: Mock
) -> None:
    """Test the discovery flow for an MCP server provided by an app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_HASSIO},
        data=ADDON_DISCOVERY_INFO,
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
    assert result["data"] == {
        CONF_URL: MCP_SERVER_URL,
        CONF_SLUG: ADDON_DISCOVERY_INFO.slug,
    }
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
    "entry_url",
    [
        pytest.param("http://1.1.1.1:9999/mcp", id="app_moved"),
        pytest.param(MCP_SERVER_URL, id="app_restarted"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_updates_url(
    hass: HomeAssistant, entry_url: str
) -> None:
    """Test discovery of an already configured app keeps its entry up to date."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDON_DISCOVERY_INFO.uuid,
        data={CONF_URL: entry_url},
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
    assert config_entry.data == {CONF_URL: MCP_SERVER_URL}


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


@respx.mock
@pytest.mark.usefixtures("mock_setup_entry")
async def test_hassio_discovery_requires_authentication(
    hass: HomeAssistant, mock_mcp_client: Mock
) -> None:
    """Test the discovered MCP server continues into the OAuth flow."""
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


async def test_reconfigure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow updates the URL."""
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_URL: MCP_SERVER_URL}
    assert config_entry.title == TEST_API_NAME


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
async def test_reconfigure_mcp_client_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test the reconfigure flow handles client errors."""
    result = await config_entry.start_reconfigure_flow(hass)
    mock_mcp_client.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Reset and retry successfully
    mock_mcp_client.side_effect = None
    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_URL: MCP_SERVER_URL}


async def test_reconfigure_invalid_url(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow rejects an invalid URL."""
    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "not a url"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}
    url_marker = next(
        key for key in result["data_schema"].schema if key.schema == CONF_URL
    )
    assert url_marker.description == {"suggested_value": "not a url"}

    # Retry with a valid URL
    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {CONF_URL: MCP_SERVER_URL}


async def test_reconfigure_missing_capabilities(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow aborts when the server lacks capabilities."""
    result = await config_entry.start_reconfigure_flow(hass)

    response = Mock()
    response.server_info.name = TEST_API_NAME
    response.capabilities.tools = None
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_capabilities"


async def test_reconfigure_duplicate_url(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow aborts when the new URL matches another entry."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: MCP_SERVER_URL},
        title="Other Server",
    )
    other_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "credential")
async def test_reconfigure_oauth(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test reconfigure keeps the token when the origin is unchanged."""
    result = await config_entry_with_auth.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    # Reconfigure on the same origin with a different path
    RECONF_URL = "http://1.1.1.1:8080/mcp2"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: RECONF_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    data = {**config_entry_with_auth.data}
    token = data.pop(CONF_TOKEN)
    assert data == {
        "auth_implementation": AUTH_DOMAIN,
        CONF_URL: RECONF_URL,
        CONF_AUTHORIZATION_URL: OAUTH_AUTHORIZE_URL,
        CONF_TOKEN_URL: OAUTH_TOKEN_URL,
        CONF_SCOPE: ["read", "write"],
    }
    token.pop("expires_at")
    assert token == {
        CONF_ACCESS_TOKEN: "test-access-token",
        "refresh_token": "test-refresh-token",
    }


@pytest.mark.usefixtures("mock_setup_entry", "credential")
async def test_reconfigure_oauth_invalid_url(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test reconfigure with OAuth rejects an invalid URL without touching the token."""
    result = await config_entry_with_auth.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "not a url"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_URL: "invalid_url"}
    assert "auth_implementation" in config_entry_with_auth.data
    assert CONF_TOKEN in config_entry_with_auth.data

    # Retry with a valid URL
    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_setup_entry", "credential")
async def test_reconfigure_oauth_different_origin_no_auth(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test reconfigure to a different origin drops the stored OAuth fields."""
    result = await config_entry_with_auth.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    # Reconfigure on a different origin
    RECONF_URL = "http://192.0.2.1:8080/mcp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: RECONF_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry_with_auth.data == {CONF_URL: RECONF_URL}
    assert config_entry_with_auth.title == TEST_API_NAME


@pytest.mark.usefixtures("credential", "current_request_with_host")
@respx.mock
async def test_reconfigure_oauth_different_origin_reauth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    config_entry_with_auth: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test reconfigure to a different origin re-authenticates on 401."""
    # Reconfigure on a different origin
    RECONF_URL = "http://192.0.2.1:8080/mcp"

    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required",
        request=None,
        response=httpx2.Response(
            401,
            headers={
                "WWW-Authenticate": (
                    'Bearer resource_metadata="'
                    "http://192.0.2.1:8080/.well-known/oauth-protected-resource/mcp"
                    '", scope="read write"'
                )
            },
        ),
    )
    respx.get("http://192.0.2.1:8080/.well-known/oauth-protected-resource/mcp").mock(
        return_value=httpx2.Response(
            200,
            json={
                "resource": RECONF_URL,
                "authorization_servers": [AUTHORIZATION_SERVER],
                "scopes_supported": SCOPES_SUPPORTED,
                "bearer_methods_supported": ["header"],
            },
        )
    )
    respx.get(OAUTH_AUTHORIZATION_SERVER_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await config_entry_with_auth.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: RECONF_URL},
    )
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
        scopes=["read", "write"],
    )

    # The new server accepts the freshly acquired token
    mock_mcp_client.side_effect = None
    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    data = {**config_entry_with_auth.data}
    token = data.pop(CONF_TOKEN)
    assert data == {
        "auth_implementation": AUTH_DOMAIN,
        CONF_URL: RECONF_URL,
        CONF_AUTHORIZATION_URL: OAUTH_AUTHORIZE_URL,
        CONF_TOKEN_URL: OAUTH_TOKEN_URL,
        CONF_SCOPE: ["read", "write"],
    }
    token.pop("expires_at")
    assert token == OAUTH_TOKEN_PAYLOAD

    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_oauth_implementation_unavailable(
    hass: HomeAssistant,
    config_entry_with_auth: MockConfigEntry,
) -> None:
    """Test reconfigure aborts when the OAuth provider is unavailable."""
    result = await config_entry_with_auth.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.mcp.async_get_config_entry_implementation",
        side_effect=ConfigEntryNotReady,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: MCP_SERVER_URL},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth2_implementation_unavailable"


async def test_reconfigure_oauth_unknown_implementation(
    hass: HomeAssistant,
) -> None:
    """Test reconfigure aborts when the stored implementation no longer exists."""
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

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth2_implementation_unavailable"


@pytest.mark.usefixtures("credential")
async def test_reconfigure_oauth_token_refresh_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reconfigure shows an error when the token cannot be refreshed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": AUTH_DOMAIN,
            CONF_URL: MCP_SERVER_URL,
            CONF_AUTHORIZATION_URL: OAUTH_AUTHORIZE_URL,
            CONF_TOKEN_URL: OAUTH_TOKEN_URL,
            CONF_TOKEN: {
                CONF_ACCESS_TOKEN: "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": (dt_util.utcnow() - dt.timedelta(days=1)).timestamp(),
            },
            CONF_SCOPE: ["read", "write"],
        },
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    refresh_responses = iter(
        [
            AiohttpClientMockResponse(
                "post",
                OAUTH_TOKEN_URL,
                status=HTTPStatus.BAD_REQUEST,
                json={"error": "invalid_grant"},
            ),
            AiohttpClientMockResponse(
                "post", OAUTH_TOKEN_URL, json=OAUTH_TOKEN_PAYLOAD
            ),
        ]
    )

    async def refresh_token(
        method: str, url: URL, data: Any
    ) -> AiohttpClientMockResponse:
        return next(refresh_responses)

    aioclient_mock.post(OAUTH_TOKEN_URL, side_effect=refresh_token)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # The token refresh succeeds on retry, so the flow can still finish
    response = Mock()
    response.server_info.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
