"""Test the Model Context Protocol config flow."""

import asyncio
from collections.abc import Callable
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
import httpx
import httpx2
import pytest
import respx
from yarl import URL

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    AuthImplementationNotApplicable,
    AuthorizationServer,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.mcp import async_get_config_entry_implementation
from homeassistant.components.mcp.application_credentials import (
    McpRegisteredOAuth2Implementation,
    async_get_auth_implementation,
    authorization_server_context,
)
from homeassistant.components.mcp.auth import AuthenticateHeader
from homeassistant.components.mcp.config_flow import (
    _async_registration_lock as config_flow_registration_lock,
)
from homeassistant.components.mcp.const import (
    CONF_AUTHORIZATION_URL,
    CONF_SCOPE,
    CONF_SLUG,
    CONF_TOKEN_URL,
    DCR_CLIENT_NAME,
    DOMAIN,
)
from homeassistant.components.mcp.registration import (
    ClientRegistrationError,
    RegisteredClient,
    RegisteredClientIdentity,
    async_register_dynamic_client,
    decode_registered_client_id,
    encode_registered_client_id,
    normalized_scopes,
    registered_client_auth_domain,
)
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DOMAIN,
    CONF_ID,
    CONF_TOKEN,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import (
    HomeAssistantError,
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.setup import async_setup_component

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


@pytest.mark.usefixtures("mock_setup_entry")
@respx.mock
async def test_duplicate_url_aborts_before_oauth(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """An already configured URL aborts before OAuth discovery starts."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: MCP_SERVER_URL},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(registration_endpoint="/register")
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert not mock_mcp_client.called
    assert not respx.calls


@pytest.mark.usefixtures("mock_setup_entry")
async def test_server_missing_capbilities(
    hass: HomeAssistant, mock_mcp_client: Mock
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
    response.serverInfo.name = TEST_API_NAME
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
    parsed_server = URL(MCP_SERVER_URL)
    for fallback_url in (
        str(
            parsed_server.with_path(
                f"/.well-known/oauth-protected-resource{parsed_server.path}"
            )
        ),
        str(parsed_server.with_path("/.well-known/oauth-protected-resource")),
    ):
        respx.get(fallback_url).mock(return_value=httpx2.Response(status_code=404))
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

    result = await perform_oauth_flow(
        hass, aioclient_mock, hass_client_no_auth, result, scopes=SCOPES
    )

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
    response.serverInfo.name = TEST_API_NAME
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
    response.serverInfo.name = TEST_API_NAME
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

    response = Mock()
    response.serverInfo.name = TEST_API_NAME
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
    response.serverInfo.name = TEST_API_NAME
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
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"]
    assert result["result"].unique_id == ADDON_DISCOVERY_INFO.uuid
    assert len(mock_setup_entry.mock_calls) == 1


def _authorization_server_metadata(
    *,
    registration_endpoint: str | None = None,
    auth_methods: list[str] | None = None,
    authorize_url: str = OAUTH_AUTHORIZE_URL,
    token_url: str = OAUTH_TOKEN_URL,
    scopes: list[str] | None = None,
) -> httpx2.Response:
    """Build an authorization server metadata response."""
    payload: dict[str, Any] = {
        "authorization_endpoint": authorize_url,
        "token_endpoint": token_url,
        "scopes_supported": SCOPES if scopes is None else scopes,
    }
    if registration_endpoint is not None:
        payload["registration_endpoint"] = registration_endpoint
    if auth_methods is not None:
        payload["token_endpoint_auth_methods_supported"] = auth_methods
    return httpx2.Response(status_code=200, json=payload)


REGISTERED_CLIENT_ID = "registered-client-id"
REGISTERED_CLIENT_SECRET = "registered-secret"


@pytest.mark.usefixtures("current_request_with_host", "credential")
@respx.mock
async def test_without_registration_endpoint_uses_application_credentials(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """Servers without a registration endpoint keep the application credential flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata()
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "credentials_choice"
    assert all(call.request.method == "GET" for call in respx.calls)


@pytest.mark.parametrize(
    (
        "auth_methods",
        "registration_endpoint",
        "expected_registration_url",
        "registration_status",
        "expected_method",
        "client_secret",
        "secret_in_body",
        "expect_basic",
    ),
    [
        pytest.param(
            None,
            "/register",
            f"{MCP_SERVER_BASE_URL}/register",
            200,
            "client_secret_basic",
            REGISTERED_CLIENT_SECRET,
            False,
            True,
            id="omitted_methods_default_basic",
        ),
        pytest.param(
            ["none", "client_secret_post"],
            f"{AUTHORIZATION_SERVER}/register",
            f"{AUTHORIZATION_SERVER}/register",
            201,
            "none",
            "",
            False,
            False,
            id="public_preferred",
        ),
        pytest.param(
            ["client_secret_post", "client_secret_basic"],
            f"{AUTHORIZATION_SERVER}/register",
            f"{AUTHORIZATION_SERVER}/register",
            201,
            "client_secret_post",
            REGISTERED_CLIENT_SECRET,
            True,
            False,
            id="confidential_post",
        ),
        pytest.param(
            ["client_secret_basic"],
            f"{AUTHORIZATION_SERVER}/register",
            f"{AUTHORIZATION_SERVER}/register",
            201,
            "client_secret_basic",
            REGISTERED_CLIENT_SECRET,
            False,
            True,
            id="confidential_basic",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "credential")
@respx.mock
async def test_dynamic_client_registration(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_mcp_client: Mock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
    auth_methods: list[str] | None,
    registration_endpoint: str,
    expected_registration_url: str,
    registration_status: int,
    expected_method: str,
    client_secret: str,
    secret_in_body: bool,
    expect_basic: bool,
) -> None:
    """Register a client when metadata includes a registration endpoint."""
    registration = respx.post(expected_registration_url).mock(
        return_value=httpx2.Response(
            registration_status,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": client_secret,
                "token_endpoint_auth_method": expected_method,
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint=registration_endpoint,
            auth_methods=auth_methods,
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert registration.called
    registered_payload = json.loads(registration.calls.last.request.content)
    assert registered_payload["token_endpoint_auth_method"] == expected_method
    assert registered_payload["redirect_uris"] == [OAUTH_CALLBACK_URL]
    assert registered_payload["application_type"] == "web"
    assert registered_payload["client_name"] == DCR_CLIENT_NAME
    assert registered_payload["grant_types"] == ["authorization_code", "refresh_token"]
    assert registered_payload["response_types"] == ["code"]
    assert registered_payload["scope"] == "read write"

    authorize_url = URL(result["url"])
    assert authorize_url.query["client_id"] == REGISTERED_CLIENT_ID
    assert authorize_url.query["code_challenge_method"] == "S256"
    assert authorize_url.query["code_challenge"]
    assert authorize_url.query["scope"] == "read write"
    state = authorize_url.query["state"]

    aioclient_mock.post(OAUTH_TOKEN_URL, json=OAUTH_TOKEN_PAYLOAD)
    client = await hass_client_no_auth()
    resp = await client.get(f"{CALLBACK_PATH}?code={OAUTH_CODE}&state={state}")
    assert resp.status == 200

    mock_mcp_client.side_effect = None
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["data"]["auth_implementation"] != AUTH_DOMAIN
    assert result["data"][CONF_URL] == MCP_SERVER_URL
    assert result["data"][CONF_AUTHORIZATION_URL] == OAUTH_AUTHORIZE_URL
    assert result["data"][CONF_TOKEN_URL] == OAUTH_TOKEN_URL
    assert result["result"]
    assert result["result"].unique_id is None

    token_method, _token_url, token_body, headers = aioclient_mock.mock_calls[-1]
    assert token_method.lower() == "post"
    assert token_body["grant_type"] == "authorization_code"
    assert token_body["client_id"] == REGISTERED_CLIENT_ID
    assert token_body["code_verifier"]
    assert (token_body.get("client_secret") == client_secret) is secret_in_body
    authorization = (headers or {}).get("Authorization", "")
    assert authorization.startswith("Basic ") is expect_basic

    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    credential = stored[result["data"]["auth_implementation"]]
    identity = decode_registered_client_id(credential.client_id)
    assert identity is not None
    assert identity.client_id == REGISTERED_CLIENT_ID
    assert identity.method == expected_method
    assert identity.authorize_url == OAUTH_AUTHORIZE_URL
    assert identity.token_url == OAUTH_TOKEN_URL
    assert credential.client_secret == client_secret
    assert credential.name == DCR_CLIENT_NAME
    stored_item = next(
        item
        for item in hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_items()
        if item[CONF_ID] == result["data"]["auth_implementation"]
    )
    assert stored_item["auth_domain"] == stored_item[CONF_ID]

    implementation = await async_get_config_entry_implementation(hass, result["result"])
    assert isinstance(implementation, McpRegisteredOAuth2Implementation)
    assert implementation.client_id == REGISTERED_CLIENT_ID
    assert implementation.token_endpoint_auth_method == expected_method
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("response", "expected_reason"),
    [
        pytest.param(
            httpx2.Response(400, json={"error": "invalid_client_metadata"}),
            "oauth_registration_failed",
            id="http_400",
        ),
        pytest.param(
            httpx2.Response(500, text="unavailable"),
            "oauth_registration_failed",
            id="http_500",
        ),
        pytest.param(
            httpx2.Response(201, json={"client_secret": "secret"}),
            "oauth_registration_failed",
            id="missing_client_id",
        ),
        pytest.param(
            httpx2.Response(200, text="not-json"),
            "oauth_registration_failed",
            id="invalid_json",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_dynamic_client_registration_http_error(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    response: httpx2.Response,
    expected_reason: str,
) -> None:
    """Registration endpoint errors abort before the authorize step."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(return_value=response)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(registration_endpoint="/register")
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    assert stored == {}


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        pytest.param(
            httpx2.TimeoutException("timeout"),
            "timeout_connect",
            id="timeout",
        ),
        pytest.param(
            httpx2.ConnectError("down"),
            "cannot_connect",
            id="connect_error",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_dynamic_client_registration_transport_error(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    side_effect: Exception,
    expected_reason: str,
) -> None:
    """Registration transport errors use the same abort reasons as discovery."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(side_effect=side_effect)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(registration_endpoint="/register")
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.parametrize(
    ("patch_target", "replacement", "expected_reason"),
    [
        pytest.param(
            "homeassistant.components.mcp.config_flow.async_get_redirect_uri",
            Mock(side_effect=RuntimeError("no url")),
            "no_url_available",
            id="redirect_uri_unavailable",
        ),
        pytest.param(
            "homeassistant.components.mcp.config_flow.async_import_client_credential",
            AsyncMock(side_effect=ValueError("cannot store")),
            "oauth_registration_failed",
            id="import_rejected",
        ),
        pytest.param(
            "homeassistant.components.mcp.config_flow.async_get_implementations",
            AsyncMock(return_value={}),
            "oauth_registration_failed",
            id="implementation_missing",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_dynamic_client_registration_error_recovery(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    patch_target: str,
    replacement: Mock,
    expected_reason: str,
) -> None:
    """Registration recovery aborts instead of continuing the authorize step."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    with patch(patch_target, new=replacement):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: MCP_SERVER_URL},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


PATH_MCP_URL = "http://1.1.1.1:8080/mcp/babybuddy"
PATH_RESOURCE_METADATA_URL = (
    "http://1.1.1.1:8080/.well-known/oauth-protected-resource/mcp/babybuddy"
)
ROOT_RESOURCE_METADATA_URL = "http://1.1.1.1:8080/.well-known/oauth-protected-resource"
PATH_AUTHORIZATION_SERVER = "https://babybuddy-auth.example"


@pytest.mark.usefixtures("mock_setup_entry")
@respx.mock
async def test_path_mcp_url_uses_header_resource_metadata(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """Path-specific metadata wins when the root document describes another path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required",
        request=None,
        response=httpx2.Response(
            401,
            headers={
                "WWW-Authenticate": (
                    f'Bearer resource_metadata="{PATH_RESOURCE_METADATA_URL}"'
                )
            },
        ),
    )
    respx.get(PATH_RESOURCE_METADATA_URL).mock(
        return_value=httpx2.Response(
            200,
            json={
                "resource": PATH_MCP_URL,
                "authorization_servers": [PATH_AUTHORIZATION_SERVER],
                "scopes_supported": ["babybuddy"],
            },
        )
    )
    respx.get(ROOT_RESOURCE_METADATA_URL).mock(
        return_value=httpx2.Response(
            200,
            json={
                "resource": "http://1.1.1.1:8080/mcp",
                "authorization_servers": ["https://root-auth.example"],
            },
        )
    )
    respx.get(
        f"{PATH_AUTHORIZATION_SERVER}/.well-known/oauth-authorization-server"
    ).mock(return_value=OAUTH_SERVER_METADATA_RESPONSE)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: PATH_MCP_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"
    assert any(
        str(call.request.url) == PATH_RESOURCE_METADATA_URL for call in respx.calls
    )


def _sdk_unauthorized() -> httpx.HTTPStatusError:
    """Build the httpx (not httpx2) 401 the MCP SDK raises."""
    request = httpx.Request("POST", MCP_SERVER_URL)
    response = httpx.Response(
        401,
        headers={
            "WWW-Authenticate": (
                'Bearer resource_metadata="https://example.com/custom-discovery"'
            )
        },
        request=request,
    )
    return httpx.HTTPStatusError("Unauthorized", request=request, response=response)


def _identity_error(error: httpx.HTTPStatusError) -> httpx.HTTPStatusError:
    """Return the SDK error unchanged."""
    return error


def _wrap_task_group(error: httpx.HTTPStatusError) -> ExceptionGroup:
    """Wrap an error the way an anyio TaskGroup does."""
    return ExceptionGroup("unhandled errors in a TaskGroup", [error])


def _wrap_nested_group(error: httpx.HTTPStatusError) -> ExceptionGroup:
    """Wrap an error in the nested group the streamable HTTP client raises."""
    return ExceptionGroup(
        "unhandled errors in a TaskGroup",
        [ExceptionGroup("mcp.client.streamable_http", [error])],
    )


def _wrap_cause(error: httpx.HTTPStatusError) -> ExceptionGroup:
    """Hide the status error on the cause chain of the task-group exception."""
    wrapper = RuntimeError("streamable http task failed")
    wrapper.__cause__ = error
    return ExceptionGroup("unhandled errors in a TaskGroup", [wrapper])


@pytest.mark.parametrize(
    "wrap",
    [
        pytest.param(_identity_error, id="httpx_status"),
        pytest.param(_wrap_task_group, id="task_group"),
        pytest.param(_wrap_nested_group, id="nested_task_group"),
        pytest.param(_wrap_cause, id="nested_cause"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
@respx.mock
async def test_sdk_httpx_unauthorized_starts_auth_discovery(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    wrap: Callable[[httpx.HTTPStatusError], Exception],
) -> None:
    """A 401 from the MCP SDK httpx package starts OAuth discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = wrap(_sdk_unauthorized())
    respx.get("https://example.com/custom-discovery").mock(
        return_value=OAUTH_PROTECTED_RESOURCE_METADATA_RESPONSE
    )
    respx.get(OAUTH_AUTHORIZATION_SERVER_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("mock_setup_entry")
@respx.mock
async def test_validate_input_accepts_sdk_httpx_status_error(
    hass: HomeAssistant,
) -> None:
    """validate_input maps httpx.HTTPStatusError 401 to authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    client = AsyncMock()
    client.__aenter__.side_effect = _sdk_unauthorized()
    respx.get("https://example.com/custom-discovery").mock(
        return_value=OAUTH_PROTECTED_RESOURCE_METADATA_RESPONSE
    )
    respx.get(OAUTH_AUTHORIZATION_SERVER_DISCOVERY_ENDPOINT).mock(
        return_value=OAUTH_SERVER_METADATA_RESPONSE
    )

    with patch(
        "homeassistant.components.mcp.config_flow.mcp_client",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: MCP_SERVER_URL},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_credentials"


@pytest.mark.usefixtures("current_request_with_host", "credential")
@respx.mock
async def test_dynamic_client_registration_reuses_existing_client(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """A later attempt reuses the client already registered for this server."""
    registration = respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    async def _start_flow() -> config_entries.ConfigFlowResult:
        started = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        mock_mcp_client.side_effect = httpx2.HTTPStatusError(
            "Authentication required", request=None, response=httpx2.Response(401)
        )
        return await hass.config_entries.flow.async_configure(
            started["flow_id"],
            {CONF_URL: MCP_SERVER_URL},
        )

    first = await _start_flow()
    assert first["type"] is FlowResultType.EXTERNAL_STEP
    assert registration.call_count == 1
    hass.config_entries.flow.async_abort(first["flow_id"])

    second = await _start_flow()
    assert second["type"] is FlowResultType.EXTERNAL_STEP
    assert registration.call_count == 1
    assert URL(second["url"]).query["client_id"] == REGISTERED_CLIENT_ID
    registered = [
        item
        for item in hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_items()
        if decode_registered_client_id(item[CONF_CLIENT_ID]) is not None
    ]
    assert len(registered) == 1


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_registration_records_callback_and_scopes(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """A stored client remembers the callback and scopes it was registered for."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "client_secret_post",
                "redirect_uris": [OAUTH_CALLBACK_URL, "https://other.example/callback"],
                "scope": "write read extra",
                "client_secret_expires_at": 0,
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    registered = [
        item
        for item in hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_items()
        if (identity := decode_registered_client_id(item[CONF_CLIENT_ID])) is not None
    ]
    assert len(registered) == 1
    identity = decode_registered_client_id(registered[0][CONF_CLIENT_ID])
    assert identity is not None
    assert identity.redirect_uri == OAUTH_CALLBACK_URL
    assert identity.scopes == ("read", "write")


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_different_scopes_register_another_client(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """Another MCP resource on the same authorization server keeps its own client."""
    registration = respx.post(f"{AUTHORIZATION_SERVER}/register").mock(
        side_effect=[
            httpx2.Response(
                201,
                json={
                    "client_id": "client-read",
                    "client_secret": "secret-read",
                    "token_endpoint_auth_method": "client_secret_post",
                },
            ),
            httpx2.Response(
                201,
                json={
                    "client_id": "client-write",
                    "client_secret": "secret-write",
                    "token_endpoint_auth_method": "client_secret_post",
                },
            ),
        ]
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint=f"{AUTHORIZATION_SERVER}/register",
            auth_methods=["client_secret_post"],
            scopes=["read"],
        )
    )
    respx.get(
        f"{MCP_SERVER_BASE_URL}/.well-known/oauth-authorization-server/mcp/babybuddy"
    ).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint=f"{AUTHORIZATION_SERVER}/register",
            auth_methods=["client_secret_post"],
            scopes=["write"],
        )
    )

    async def _start(mcp_url: str) -> config_entries.ConfigFlowResult:
        started = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        mock_mcp_client.side_effect = httpx2.HTTPStatusError(
            "Authentication required", request=None, response=httpx2.Response(401)
        )
        return await hass.config_entries.flow.async_configure(
            started["flow_id"],
            {CONF_URL: mcp_url},
        )

    first = await _start(MCP_SERVER_URL)
    second = await _start(PATH_MCP_URL)

    assert first["type"] is FlowResultType.EXTERNAL_STEP
    assert second["type"] is FlowResultType.EXTERNAL_STEP
    assert URL(first["url"]).query["client_id"] == "client-read"
    assert URL(second["url"]).query["client_id"] == "client-write"
    assert registration.call_count == 2


@pytest.mark.usefixtures("mock_setup_entry")
@respx.mock
async def test_different_redirect_uri_registers_another_client(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """A changed callback URI is not reused from an older registration."""
    registration = respx.post(f"{AUTHORIZATION_SERVER}/register").mock(
        side_effect=[
            httpx2.Response(
                201,
                json={
                    "client_id": "client-first",
                    "client_secret": "secret-first",
                    "token_endpoint_auth_method": "client_secret_post",
                },
            ),
            httpx2.Response(
                201,
                json={
                    "client_id": "client-second",
                    "client_secret": "secret-second",
                    "token_endpoint_auth_method": "client_secret_post",
                },
            ),
        ]
    )

    def _metadata(_request: httpx2.Request) -> httpx2.Response:
        return _authorization_server_metadata(
            registration_endpoint=f"{AUTHORIZATION_SERVER}/register",
            auth_methods=["client_secret_post"],
        )

    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(side_effect=_metadata)
    respx.get(
        f"{MCP_SERVER_BASE_URL}/.well-known/oauth-authorization-server/mcp/babybuddy"
    ).mock(side_effect=_metadata)

    async def _start(mcp_url: str) -> config_entries.ConfigFlowResult:
        started = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        mock_mcp_client.side_effect = httpx2.HTTPStatusError(
            "Authentication required", request=None, response=httpx2.Response(401)
        )
        return await hass.config_entries.flow.async_configure(
            started["flow_id"],
            {CONF_URL: mcp_url},
        )

    # Authorize uses the callback stored at registration, so each flow looks
    # the current redirect up once.
    redirects = [
        OAUTH_CALLBACK_URL,
        "https://other.example/auth/external/callback",
    ]

    def _redirect(_hass: HomeAssistant) -> str:
        return redirects.pop(0)

    with (
        patch(
            "homeassistant.components.mcp.config_flow.async_get_redirect_uri",
            side_effect=_redirect,
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_redirect_uri",
            side_effect=_redirect,
        ),
    ):
        first = await _start(MCP_SERVER_URL)
        second = await _start(PATH_MCP_URL)

    assert first["type"] is FlowResultType.EXTERNAL_STEP
    assert second["type"] is FlowResultType.EXTERNAL_STEP
    assert URL(first["url"]).query["client_id"] == "client-first"
    assert URL(second["url"]).query["client_id"] == "client-second"
    assert registration.call_count == 2


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_client_without_recorded_metadata_is_not_reused(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """A client stored before callback and scopes were recorded is not reused."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    encoded = encode_registered_client_id(
        RegisteredClientIdentity(
            authorize_url=OAUTH_AUTHORIZE_URL,
            token_url=OAUTH_TOKEN_URL,
            client_id="legacy-client",
            method="client_secret_post",
        )
    )
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(encoded, "legacy-secret", DCR_CLIENT_NAME),
        registered_client_auth_domain(encoded),
    )
    registration = respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert registration.call_count == 1
    assert URL(result["url"]).query["client_id"] == REGISTERED_CLIENT_ID


class _RegistrationLockGate:
    """Wrap the production lock and signal when a second flow reaches it."""

    def __init__(
        self,
        inner: asyncio.Lock,
        second_waiting: asyncio.Event,
        entries: list[int],
    ) -> None:
        """Initialize the gate around one authorization-server lock."""
        self._inner = inner
        self._second_waiting = second_waiting
        self._entries = entries

    async def __aenter__(self) -> None:
        """Enter the production lock, after noting a second waiter."""
        self._entries[0] += 1
        if self._entries[0] == 2:
            # Set before acquiring. The current task then waits on the real
            # lock, so the test resumes only once this flow is blocked.
            self._second_waiting.set()
        await self._inner.acquire()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        """Release the production lock."""
        self._inner.release()


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_concurrent_flows_register_one_client(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """Two flows for one authorization server share a single registration."""
    release = asyncio.Event()
    entered = asyncio.Event()
    second_waiting = asyncio.Event()
    entries = [0]
    calls = 0
    original_lock = config_flow_registration_lock

    async def _register(*args: Any, **kwargs: Any) -> RegisteredClient:
        nonlocal calls
        calls += 1
        entered.set()
        await release.wait()
        return RegisteredClient(
            REGISTERED_CLIENT_ID,
            REGISTERED_CLIENT_SECRET,
            "client_secret_post",
        )

    def _lock(
        lock_hass: HomeAssistant, authorize_url: str, token_url: str
    ) -> _RegistrationLockGate:
        return _RegistrationLockGate(
            original_lock(lock_hass, authorize_url, token_url),
            second_waiting,
            entries,
        )

    def _metadata(_request: httpx2.Request) -> httpx2.Response:
        return _authorization_server_metadata(
            registration_endpoint=f"{AUTHORIZATION_SERVER}/register",
            auth_methods=["client_secret_post"],
        )

    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(side_effect=_metadata)
    respx.get(
        f"{MCP_SERVER_BASE_URL}/.well-known/oauth-authorization-server/mcp/babybuddy"
    ).mock(side_effect=_metadata)

    async def _start(mcp_url: str) -> config_entries.ConfigFlowResult:
        started = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        mock_mcp_client.side_effect = httpx2.HTTPStatusError(
            "Authentication required", request=None, response=httpx2.Response(401)
        )
        return await hass.config_entries.flow.async_configure(
            started["flow_id"],
            {CONF_URL: mcp_url},
        )

    with (
        patch(
            "homeassistant.components.mcp.config_flow._async_registration_lock",
            side_effect=_lock,
        ),
        patch(
            "homeassistant.components.mcp.config_flow.async_register_dynamic_client",
            side_effect=_register,
        ),
    ):
        first = asyncio.create_task(_start(MCP_SERVER_URL))
        await entered.wait()
        second = asyncio.create_task(_start(PATH_MCP_URL))
        await second_waiting.wait()
        assert calls == 1
        release.set()
        first_result, second_result = await asyncio.gather(first, second)

    assert calls == 1
    assert first_result["type"] is FlowResultType.EXTERNAL_STEP
    assert second_result["type"] is FlowResultType.EXTERNAL_STEP
    assert URL(first_result["url"]).query["client_id"] == REGISTERED_CLIENT_ID
    assert URL(second_result["url"]).query["client_id"] == REGISTERED_CLIENT_ID


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param(
            {"redirect_uris": ["https://other.example/callback"]},
            id="callback_missing",
        ),
        pytest.param({"redirect_uris": []}, id="callback_list_empty"),
        pytest.param(
            {"redirect_uris": "https://example.com/callback"},
            id="callback_not_a_list",
        ),
        pytest.param({"redirect_uris": None}, id="callback_null"),
        pytest.param({"scope": "read"}, id="scope_too_narrow"),
        pytest.param({"scope": 1}, id="scope_not_a_string"),
        pytest.param({"scope": None}, id="scope_null"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_registration_response_metadata_must_match_request(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    extra: dict[str, Any],
) -> None:
    """Registration fails when the server does not accept the callback or scopes."""
    body = {
        "client_id": REGISTERED_CLIENT_ID,
        "client_secret": REGISTERED_CLIENT_SECRET,
        "token_endpoint_auth_method": "client_secret_post",
        **extra,
    }
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(201, json=body)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_registration_failed"
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    assert stored == {}


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_partial_registration_response_does_not_log_secrets(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A partial registration response does not log issued secrets."""
    client_secret = "issued-client-secret"
    registration_access_token = "issued-registration-access-token"
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": client_secret,
                "registration_access_token": registration_access_token,
                "token_endpoint_auth_method": "client_secret_post",
                # Invalid URLs force the partial-response path. Their values are
                # the secrets, which the default validation error would print.
                "client_uri": client_secret,
                "logo_uri": registration_access_token,
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.mcp.registration"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: MCP_SERVER_URL},
        )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "client_uri: url_parsing" in caplog.text
    assert "logo_uri: url_parsing" in caplog.text
    assert client_secret not in caplog.text
    assert registration_access_token not in caplog.text


@pytest.mark.parametrize(
    ("expires_at", "expected_reason"),
    [
        pytest.param(1_700_000_000, "oauth_secret_expires", id="finite_expiry"),
        pytest.param(-1, "oauth_registration_failed", id="negative_expiry"),
        pytest.param(True, "oauth_registration_failed", id="boolean_expiry"),
        pytest.param("3600", "oauth_registration_failed", id="string_expiry"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_expiring_client_secret_is_not_stored(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    expires_at: Any,
    expected_reason: str,
) -> None:
    """A finite or invalid client secret lifetime aborts before the secret is stored."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "client_secret_post",
                "client_secret_expires_at": expires_at,
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    assert stored == {}


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_in_use_registered_credential_cannot_be_deleted(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Deleting a registered client in use by a config entry is refused."""
    respx.post(f"{AUTHORIZATION_SERVER}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint=f"{AUTHORIZATION_SERVER}/register",
            auth_methods=["client_secret_post"],
        )
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP

    authorize_url = URL(result["url"])
    state = authorize_url.query["state"]
    aioclient_mock.post(OAUTH_TOKEN_URL, json=OAUTH_TOKEN_PAYLOAD)
    client = await hass_client_no_auth()
    resp = await client.get(f"{CALLBACK_PATH}?code={OAUTH_CODE}&state={state}")
    assert resp.status == 200

    mock_mcp_client.side_effect = None
    response = Mock()
    response.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = response
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"]

    storage = hass.data[APPLICATION_CREDENTIALS_DOMAIN]
    item_id = result["data"]["auth_implementation"]
    assert any(item[CONF_ID] == item_id for item in storage.async_items())
    with pytest.raises(HomeAssistantError, match="Cannot delete credential in use"):
        await storage.async_delete_item(item_id)

    await hass.config_entries.async_remove(result["result"].entry_id)
    await storage.async_delete_item(item_id)
    assert all(item[CONF_ID] != item_id for item in storage.async_items())


@pytest.mark.parametrize(
    "auth_methods",
    [
        pytest.param([], id="empty_list"),
        pytest.param(["private_key_jwt"], id="unsupported_method"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_explicit_unsupported_auth_methods_do_not_register(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    auth_methods: list[str],
) -> None:
    """An explicit auth-method list with nothing usable does not register."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(500, text="should not be called")
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=auth_methods,
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_registration_failed"
    assert all(call.request.method == "GET" for call in respx.calls)
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    assert stored == {}


@pytest.mark.parametrize(
    "auth_methods",
    [
        pytest.param(None, id="explicit_null"),
        pytest.param("client_secret_basic", id="string"),
        pytest.param(["client_secret_basic", 1], id="mixed_list"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_malformed_auth_methods_do_not_default_to_basic(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    auth_methods: Any,
) -> None:
    """Malformed auth-method metadata is not the RFC 8414 omitted default."""
    registration = respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(500, text="should not be called")
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    metadata = _authorization_server_metadata(registration_endpoint="/register")
    payload = metadata.json()
    payload["token_endpoint_auth_methods_supported"] = auth_methods
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=httpx2.Response(200, json=payload)
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_registration_failed"
    assert not registration.called


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_unsupported_registration_response_auth_method(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """An explicit unsupported method in the registration response is rejected."""
    registration = respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "private_key_jwt",
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert registration.called
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_registration_failed"
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    assert stored == {}


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_omitted_registration_response_auth_method_keeps_requested(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """A registration response that omits the auth method keeps the request."""
    registration = respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    registered_payload = json.loads(registration.calls.last.request.content)
    assert registered_payload["token_endpoint_auth_method"] == "client_secret_post"
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    auth_domain, credential = next(iter(stored.items()))
    identity = decode_registered_client_id(credential.client_id)
    assert identity is not None
    assert identity.method == "client_secret_post"
    with authorization_server_context(
        AuthorizationServer(OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL)
    ):
        implementation = await async_get_auth_implementation(
            hass, auth_domain, credential
        )
    assert isinstance(implementation, McpRegisteredOAuth2Implementation)
    assert implementation.client_id == REGISTERED_CLIENT_ID
    assert implementation.token_endpoint_auth_method == "client_secret_post"


@pytest.mark.parametrize(
    "secret_payload",
    [
        pytest.param({}, id="omitted"),
        pytest.param({"client_secret": None}, id="null"),
        pytest.param({"client_secret": ""}, id="empty"),
        pytest.param({"client_secret": False}, id="false"),
        pytest.param({"client_secret": 0}, id="zero"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_confidential_registration_requires_client_secret(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    secret_payload: dict[str, Any],
) -> None:
    """A confidential client without a string secret is not stored."""
    body = {
        "client_id": REGISTERED_CLIENT_ID,
        "token_endpoint_auth_method": "client_secret_post",
        **secret_payload,
    }
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(201, json=body)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_registration_failed"
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    assert stored == {}


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_public_registration_may_omit_client_secret(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """A public client may omit client_secret."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "token_endpoint_auth_method": "none",
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["none"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_public_client_ignores_echoed_secret_expiry(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """A public client does not abort when an unused secret has an expiry."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "none",
                "client_secret_expires_at": 1_700_000_000,
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["none"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP


@pytest.mark.parametrize(
    ("client_id_a", "client_id_b"),
    [
        pytest.param(
            REGISTERED_CLIENT_ID,
            REGISTERED_CLIENT_ID,
            id="same_client_id",
        ),
        pytest.param("Client ID", "client_id", id="slug_equivalent_client_ids"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_registered_client_identity_is_scoped_to_authorization_server(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    client_id_a: str,
    client_id_b: str,
) -> None:
    """Two authorization servers cannot share one stored client secret."""
    servers = (
        (
            "https://auth-a.example/authorize",
            "https://auth-a.example/token",
            "https://auth-a.example/register",
            client_id_a,
            "secret-a",
        ),
        (
            "https://auth-b.example/authorize",
            "https://auth-b.example/token",
            "https://auth-b.example/register",
            client_id_b,
            "secret-b",
        ),
    )
    discovery = respx.get(OAUTH_DISCOVERY_ENDPOINT)
    for authorize_url, token_url, register_url, client_id, secret in servers:
        discovery.mock(
            return_value=_authorization_server_metadata(
                registration_endpoint=register_url,
                auth_methods=["client_secret_post"],
                authorize_url=authorize_url,
                token_url=token_url,
            )
        )
        respx.post(register_url).mock(
            return_value=httpx2.Response(
                201,
                json={
                    "client_id": client_id,
                    "client_secret": secret,
                    "token_endpoint_auth_method": "client_secret_post",
                },
            )
        )
        started = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        mock_mcp_client.side_effect = httpx2.HTTPStatusError(
            "Authentication required", request=None, response=httpx2.Response(401)
        )
        result = await hass.config_entries.flow.async_configure(
            started["flow_id"],
            {CONF_URL: MCP_SERVER_URL},
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert URL(result["url"]).query["client_id"] == client_id

    items = [
        item
        for item in hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_items()
        if decode_registered_client_id(item[CONF_CLIENT_ID]) is not None
    ]
    assert len(items) == 2
    item_a = next(
        item
        for item in items
        if (identity := decode_registered_client_id(item[CONF_CLIENT_ID])) is not None
        and identity.authorize_url == "https://auth-a.example/authorize"
    )
    item_b = next(
        item
        for item in items
        if (identity := decode_registered_client_id(item[CONF_CLIENT_ID])) is not None
        and identity.authorize_url == "https://auth-b.example/authorize"
    )
    identity_a = decode_registered_client_id(item_a[CONF_CLIENT_ID])
    identity_b = decode_registered_client_id(item_b[CONF_CLIENT_ID])
    assert identity_a is not None
    assert identity_b is not None
    assert identity_a.client_id == client_id_a
    assert identity_b.client_id == client_id_b
    assert item_a[CONF_CLIENT_SECRET] == "secret-a"
    assert item_b[CONF_CLIENT_SECRET] == "secret-b"
    assert item_a[CONF_ID] != item_b[CONF_ID]
    assert item_a["auth_domain"] == item_a[CONF_ID]
    assert item_b["auth_domain"] == item_b[CONF_ID]

    with authorization_server_context(
        AuthorizationServer(
            "https://auth-a.example/authorize",
            "https://auth-a.example/token",
        )
    ):
        implementation_a = await async_get_auth_implementation(
            hass,
            item_a[CONF_ID],
            ClientCredential(item_a[CONF_CLIENT_ID], item_a[CONF_CLIENT_SECRET]),
        )
    with authorization_server_context(
        AuthorizationServer(
            "https://auth-b.example/authorize",
            "https://auth-b.example/token",
        )
    ):
        implementation_b = await async_get_auth_implementation(
            hass,
            item_b[CONF_ID],
            ClientCredential(item_b[CONF_CLIENT_ID], item_b[CONF_CLIENT_SECRET]),
        )
    assert implementation_a.client_id == client_id_a
    assert implementation_a.client_secret == "secret-a"
    assert implementation_b.client_id == client_id_b
    assert implementation_b.client_secret == "secret-b"


async def test_manual_hex_client_id_is_not_decoded(
    hass: HomeAssistant,
) -> None:
    """A manual client id that is hex-encoded JSON stays that client id."""
    manual_payload = {
        "authorize_url": OAUTH_AUTHORIZE_URL,
        "client_id": "embedded-client",
        "method": "client_secret_post",
        "token_url": OAUTH_TOKEN_URL,
        "v": 1,
    }
    manual_client_id = (
        json.dumps(manual_payload, separators=(",", ":"), sort_keys=True).encode().hex()
    )
    assert decode_registered_client_id(manual_client_id) is None
    with authorization_server_context(
        AuthorizationServer(OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL)
    ):
        implementation = await async_get_auth_implementation(
            hass,
            "manual-auth-domain",
            ClientCredential(manual_client_id, "manual-secret"),
        )
    assert not isinstance(implementation, McpRegisteredOAuth2Implementation)
    assert implementation.client_id == manual_client_id


@pytest.mark.parametrize(
    ("stored_redirect", "expected_redirect"),
    [
        pytest.param(
            "https://old.example/auth/external/callback",
            "https://old.example/auth/external/callback",
            id="stored_callback",
        ),
        pytest.param(
            None,
            "https://current.example/auth/external/callback",
            id="legacy_without_callback",
        ),
    ],
)
async def test_reauth_uses_registered_redirect_uri(
    hass: HomeAssistant,
    stored_redirect: str | None,
    expected_redirect: str,
) -> None:
    """Reauth keeps the callback the client was registered with."""
    encoded = encode_registered_client_id(
        RegisteredClientIdentity(
            authorize_url=OAUTH_AUTHORIZE_URL,
            token_url=OAUTH_TOKEN_URL,
            client_id=REGISTERED_CLIENT_ID,
            method="client_secret_post",
            redirect_uri=stored_redirect,
        )
    )
    with (
        authorization_server_context(
            AuthorizationServer(OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL)
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_redirect_uri",
            return_value="https://current.example/auth/external/callback",
        ),
    ):
        implementation = await async_get_auth_implementation(
            hass,
            "auth-domain",
            ClientCredential(encoded, REGISTERED_CLIENT_SECRET),
        )
        assert isinstance(implementation, McpRegisteredOAuth2Implementation)
        assert implementation.name == DCR_CLIENT_NAME
        assert implementation.redirect_uri == expected_redirect


async def test_registered_client_is_hidden_from_other_authorization_server(
    hass: HomeAssistant,
) -> None:
    """A client issued by one authorization server is not offered for another."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    servers = (
        (
            "https://auth-a.example/authorize",
            "https://auth-a.example/token",
            "client-a",
            "secret-a",
        ),
        (
            "https://auth-b.example/authorize",
            "https://auth-b.example/token",
            "client-b",
            "secret-b",
        ),
    )
    domains: list[str] = []
    for authorize_url, token_url, client_id, secret in servers:
        encoded = encode_registered_client_id(
            RegisteredClientIdentity(
                authorize_url=authorize_url,
                token_url=token_url,
                client_id=client_id,
                method="client_secret_post",
            )
        )
        auth_domain = registered_client_auth_domain(encoded)
        domains.append(auth_domain)
        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential(encoded, secret, "Home Assistant"),
            auth_domain,
        )
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("manual-client", "manual-secret", "Manual"),
        "manual-auth-domain",
    )

    with authorization_server_context(
        AuthorizationServer(
            "https://auth-a.example/authorize",
            "https://auth-a.example/token",
        )
    ):
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            hass, DOMAIN
        )

    assert domains[0] in implementations
    assert domains[1] not in implementations
    assert "manual-auth-domain" in implementations
    visible = implementations[domains[0]]
    assert isinstance(visible, McpRegisteredOAuth2Implementation)
    assert visible.client_id == "client-a"
    assert visible.client_secret == "secret-a"
    with (
        authorization_server_context(
            AuthorizationServer(
                "https://auth-b.example/authorize",
                "https://auth-b.example/token",
            )
        ),
        pytest.raises(AuthImplementationNotApplicable),
    ):
        await async_get_auth_implementation(
            hass,
            domains[0],
            ClientCredential(
                encode_registered_client_id(
                    RegisteredClientIdentity(
                        authorize_url="https://auth-a.example/authorize",
                        token_url="https://auth-a.example/token",
                        client_id="client-a",
                        method="client_secret_post",
                    )
                ),
                "secret-a",
            ),
        )


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_two_mcp_urls_create_separate_oauth_entries(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Two MCP paths that share an OAuth client stay separate entries.

    Dynamic registration reuses one client for an authorization server, so the
    credential id is not unique per MCP URL.
    """
    registration = respx.post(f"{AUTHORIZATION_SERVER}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
    )

    def _metadata(_request: httpx2.Request) -> httpx2.Response:
        return _authorization_server_metadata(
            registration_endpoint=f"{AUTHORIZATION_SERVER}/register",
            auth_methods=["client_secret_post"],
        )

    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(side_effect=_metadata)
    respx.get(
        f"{MCP_SERVER_BASE_URL}/.well-known/oauth-authorization-server/mcp/babybuddy"
    ).mock(side_effect=_metadata)

    async def _create_entry(mcp_url: str) -> None:
        started = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        mock_mcp_client.side_effect = httpx2.HTTPStatusError(
            "Authentication required", request=None, response=httpx2.Response(401)
        )
        result = await hass.config_entries.flow.async_configure(
            started["flow_id"],
            {CONF_URL: mcp_url},
        )
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        state = URL(result["url"]).query["state"]
        aioclient_mock.post(OAUTH_TOKEN_URL, json=OAUTH_TOKEN_PAYLOAD)
        client = await hass_client_no_auth()
        resp = await client.get(f"{CALLBACK_PATH}?code={OAUTH_CODE}&state={state}")
        assert resp.status == 200
        mock_mcp_client.side_effect = None
        response = Mock()
        response.serverInfo.name = TEST_API_NAME
        mock_mcp_client.return_value.initialize.return_value = response
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"]
        assert result["result"].unique_id is None
        assert result["data"][CONF_URL] == mcp_url

    await _create_entry(MCP_SERVER_URL)
    await _create_entry(PATH_MCP_URL)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert {entry.data[CONF_URL] for entry in entries} == {MCP_SERVER_URL, PATH_MCP_URL}
    assert {entry.unique_id for entry in entries} == {None}
    assert (
        entries[0].data["auth_implementation"] == entries[1].data["auth_implementation"]
    )
    assert registration.call_count == 1


def test_normalized_scopes_treats_empty_as_omitted() -> None:
    """An omitted scope list and an empty list are the same request."""
    assert normalized_scopes(None) == ()
    assert normalized_scopes([]) == ()


def _marked_client_id(payload: dict[str, Any]) -> str:
    """Return a registration marker around an arbitrary JSON payload."""
    return "mcp-dcr:" + json.dumps(payload, separators=(",", ":")).encode().hex()


def _valid_identity_payload() -> dict[str, Any]:
    """Return a decodable registered-client payload."""
    return {
        "authorize_url": OAUTH_AUTHORIZE_URL,
        "client_id": "cid",
        "method": "none",
        "token_url": OAUTH_TOKEN_URL,
        "v": 1,
    }


@pytest.mark.parametrize(
    "client_id",
    [
        pytest.param("mcp-dcr:zz", id="bad_hex"),
        pytest.param("mcp-dcr:" + b"{".hex(), id="bad_json"),
        pytest.param(
            "mcp-dcr:" + json.dumps([1]).encode().hex(),
            id="not_object",
        ),
        pytest.param(_marked_client_id({"v": 2}), id="wrong_version"),
        pytest.param(
            _marked_client_id({**_valid_identity_payload(), "authorize_url": ""}),
            id="empty_authorize_url",
        ),
        pytest.param(
            _marked_client_id({**_valid_identity_payload(), "redirect_uri": ""}),
            id="empty_redirect_uri",
        ),
        pytest.param(
            _marked_client_id({**_valid_identity_payload(), "redirect_uri": 1}),
            id="redirect_uri_not_string",
        ),
        pytest.param(
            _marked_client_id({**_valid_identity_payload(), "scopes": "read"}),
            id="scopes_not_a_list",
        ),
        pytest.param(
            _marked_client_id({**_valid_identity_payload(), "scopes": ["read", 1]}),
            id="scopes_mixed",
        ),
    ],
)
def test_decode_registered_client_id_rejects_malformed(client_id: str) -> None:
    """A marked client id that is not a registered identity stays undecoded."""
    assert decode_registered_client_id(client_id) is None


async def test_invalid_redirect_uri_is_not_registered(hass: HomeAssistant) -> None:
    """Client metadata that is not a URL fails before the registration request."""
    with pytest.raises(ClientRegistrationError):
        await async_register_dynamic_client(
            hass,
            f"{MCP_SERVER_BASE_URL}/register",
            "not a url",
            token_endpoint_auth_methods=["client_secret_post"],
            scopes=["read"],
        )


def _resource_metadata_url() -> str:
    """Return the header URL and mock the well-known fallbacks as missing."""
    resource_metadata_url = "https://example.com/custom-discovery"
    parsed_server = URL(MCP_SERVER_URL)
    for fallback_url in (
        str(
            parsed_server.with_path(
                f"/.well-known/oauth-protected-resource{parsed_server.path}"
            )
        ),
        str(parsed_server.with_path("/.well-known/oauth-protected-resource")),
    ):
        respx.get(fallback_url).mock(return_value=httpx2.Response(status_code=404))
    return resource_metadata_url


async def _protected_resource_abort_reason(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    resource_metadata_url: str,
) -> str:
    """Start user setup and return the abort reason after resource discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )
    assert result["type"] is FlowResultType.ABORT
    return result["reason"]


@pytest.mark.parametrize(
    ("header_error", "expected_reason"),
    [
        pytest.param(
            httpx2.TimeoutException("timeout"),
            "timeout_connect",
            id="timeout",
        ),
        pytest.param(
            httpx2.HTTPStatusError(
                "server",
                request=httpx2.Request("GET", "https://example.com/custom-discovery"),
                response=httpx2.Response(500),
            ),
            "cannot_connect",
            id="server_error",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_protected_resource_fetch_error_is_preserved(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    header_error: Exception,
    expected_reason: str,
) -> None:
    """A failed resource document keeps its timeout or connection error."""
    resource_metadata_url = _resource_metadata_url()
    respx.get(resource_metadata_url).mock(side_effect=header_error)

    reason = await _protected_resource_abort_reason(
        hass, mock_mcp_client, resource_metadata_url
    )

    assert reason == expected_reason


@pytest.mark.parametrize(
    "header_response",
    [
        pytest.param(httpx2.Response(200, text="not-json"), id="not_json"),
        pytest.param(httpx2.Response(200, json=["nope"]), id="not_object"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_protected_resource_document_must_be_an_object(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    header_response: httpx2.Response,
) -> None:
    """Resource metadata that is not a JSON object is ignored."""
    resource_metadata_url = _resource_metadata_url()
    respx.get(resource_metadata_url).mock(return_value=header_response)

    reason = await _protected_resource_abort_reason(
        hass, mock_mcp_client, resource_metadata_url
    )

    assert reason == "cannot_connect"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_registration_response_must_be_an_object(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """A JSON registration response that is not an object is rejected."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(201, json=["not-an-object"])
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_registration_failed"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_public_client_rejects_non_string_secret(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """A public client with a non-string secret is not stored."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": 1,
                "token_endpoint_auth_method": "none",
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["none"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_registration_failed"
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    assert stored == {}


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_registered_client_lookup_skips_other_domains(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """Credentials for another integration are not reused as MCP clients."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    hass.data[APPLICATION_CREDENTIALS_DOMAIN].data["other-id"] = {
        CONF_DOMAIN: "other",
        CONF_CLIENT_ID: "other-client",
        CONF_CLIENT_SECRET: "other-secret",
        CONF_ID: "other-id",
    }
    registration = respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(
            201,
            json={
                "client_id": REGISTERED_CLIENT_ID,
                "client_secret": REGISTERED_CLIENT_SECRET,
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_authorization_server_metadata(
            registration_endpoint="/register",
            auth_methods=["client_secret_post"],
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert registration.call_count == 1


def _basic_auth_implementation(
    hass: HomeAssistant,
) -> McpRegisteredOAuth2Implementation:
    """Return a client_secret_basic implementation."""
    return McpRegisteredOAuth2Implementation(
        hass,
        "auth-domain",
        REGISTERED_CLIENT_ID,
        OAUTH_AUTHORIZE_URL,
        OAUTH_TOKEN_URL,
        REGISTERED_CLIENT_SECRET,
        "client_secret_basic",
        registered_redirect_uri=OAUTH_CALLBACK_URL,
    )


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            '{"error": "invalid_client", "error_description": "denied"}',
            id="description",
        ),
        pytest.param('{"error": "invalid_client"}', id="code_only"),
        pytest.param("not-json", id="not_json"),
        pytest.param("", id="empty"),
    ],
)
async def test_basic_auth_token_error_does_not_return_tokens(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    body: str,
) -> None:
    """A failed basic-auth token response is reported as reauth."""
    aioclient_mock.post(OAUTH_TOKEN_URL, status=400, text=body)
    implementation = _basic_auth_implementation(hass)

    with pytest.raises(OAuth2TokenRequestReauthError):
        await implementation._token_request({"grant_type": "refresh_token"})


async def test_basic_auth_token_connection_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A basic-auth token request that never connects is a connection error."""
    aioclient_mock.post(OAUTH_TOKEN_URL, exc=ClientError("connection failed"))
    implementation = _basic_auth_implementation(hass)

    with pytest.raises(OAuth2TokenRequestConnectionError):
        await implementation._token_request({"grant_type": "refresh_token"})


def _issued_client(**extra: Any) -> dict[str, Any]:
    """Return a registration response body."""
    return {
        "client_id": REGISTERED_CLIENT_ID,
        "client_secret": REGISTERED_CLIENT_SECRET,
        "token_endpoint_auth_method": "client_secret_post",
        **extra,
    }


def _registration_discovery(
    scopes_supported: Any,
    *,
    registration_endpoint: str = "/register",
) -> httpx2.Response:
    """Return authorization server metadata, including a non-list scope value."""
    return httpx2.Response(
        200,
        json={
            "authorization_endpoint": OAUTH_AUTHORIZE_URL,
            "token_endpoint": OAUTH_TOKEN_URL,
            "registration_endpoint": registration_endpoint,
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
            "scopes_supported": scopes_supported,
        },
    )


async def _configure_registration(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    *,
    body: dict[str, Any],
    discovery: httpx2.Response,
) -> dict[str, Any]:
    """Run user setup through discovery and registration."""
    respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(201, json=body)
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(return_value=discovery)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )


@pytest.mark.parametrize(
    ("client_id", "client_secret"),
    [
        pytest.param(
            f" {REGISTERED_CLIENT_ID}",
            REGISTERED_CLIENT_SECRET,
            id="client_id",
        ),
        pytest.param(
            REGISTERED_CLIENT_ID,
            f" {REGISTERED_CLIENT_SECRET} ",
            id="client_secret",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_whitespace_credentials_are_not_stored(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    client_id: str,
    client_secret: str,
) -> None:
    """Storage would strip an opaque id or secret, so registration aborts."""
    result = await _configure_registration(
        hass,
        mock_mcp_client,
        body=_issued_client(client_id=client_id, client_secret=client_secret),
        discovery=_registration_discovery(SCOPES),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_registration_failed"
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    assert stored == {}


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param({"grant_types": ["client_credentials"]}, id="grant_types_dropped"),
        pytest.param({"grant_types": None}, id="grant_types_null"),
        pytest.param({"grant_types": "authorization_code"}, id="grant_types_string"),
        pytest.param({"response_types": ["token"]}, id="response_types_dropped"),
        pytest.param({"response_types": None}, id="response_types_null"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_registration_response_must_keep_authorization_code(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    extra: dict[str, Any],
) -> None:
    """An explicit grant or response type list must include the code flow."""
    result = await _configure_registration(
        hass,
        mock_mcp_client,
        body=_issued_client(**extra),
        discovery=_registration_discovery(SCOPES),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth_registration_failed"
    stored = hass.data[APPLICATION_CREDENTIALS_DOMAIN].async_client_credentials(DOMAIN)
    assert stored == {}


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param({}, id="omitted"),
        pytest.param(
            {
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            },
            id="required_present",
        ),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_registration_response_may_omit_grant_types(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    extra: dict[str, Any],
) -> None:
    """Omitted grant metadata stays compatible with a client-id-only response."""
    result = await _configure_registration(
        hass,
        mock_mcp_client,
        body=_issued_client(**extra),
        discovery=_registration_discovery(SCOPES),
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP


@pytest.mark.parametrize(
    "scopes_supported",
    [
        pytest.param("read", id="string"),
        pytest.param(["read", 1], id="mixed"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_malformed_scopes_supported_aborts(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    scopes_supported: Any,
) -> None:
    """Authorization server scopes that are not a string list abort discovery."""
    registration = respx.post(f"{MCP_SERVER_BASE_URL}/register").mock(
        return_value=httpx2.Response(201, json=_issued_client())
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=_registration_discovery(scopes_supported=scopes_supported)
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: MCP_SERVER_URL},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"
    assert not registration.called


@pytest.mark.parametrize(
    "scopes_supported",
    [
        pytest.param("read", id="string"),
        pytest.param(["read", 1], id="mixed"),
    ],
)
@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_malformed_resource_scopes_abort(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    scopes_supported: Any,
) -> None:
    """Protected resource scopes that are not a string list abort discovery."""
    resource_metadata_url = _resource_metadata_url()
    respx.get(resource_metadata_url).mock(
        return_value=httpx2.Response(
            200,
            json={
                "resource": MCP_SERVER_URL,
                "authorization_servers": [AUTHORIZATION_SERVER],
                "scopes_supported": scopes_supported,
            },
        )
    )
    respx.get(f"{AUTHORIZATION_SERVER}/.well-known/oauth-authorization-server").mock(
        return_value=_registration_discovery(SCOPES)
    )
    registration = respx.post(f"{AUTHORIZATION_SERVER}/register").mock(
        return_value=httpx2.Response(201, json=_issued_client())
    )

    reason = await _protected_resource_abort_reason(
        hass, mock_mcp_client, resource_metadata_url
    )

    assert reason == "invalid_discovery_info"
    assert not registration.called


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@respx.mock
async def test_null_scopes_supported_is_omitted(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
) -> None:
    """Null scopes_supported requests no scopes instead of one per character."""
    result = await _configure_registration(
        hass,
        mock_mcp_client,
        body=_issued_client(),
        discovery=_registration_discovery(scopes_supported=None),
    )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    registered_payload = json.loads(respx.calls.last.request.content)
    assert "scope" not in registered_payload
    assert "scope" not in URL(result["url"]).query


@pytest.mark.parametrize(
    "scopes",
    [
        pytest.param("read", id="string"),
        pytest.param(["read", 1], id="mixed"),
    ],
)
async def test_registration_rejects_malformed_scopes(
    hass: HomeAssistant,
    scopes: Any,
) -> None:
    """Registration does not turn a scope string into per-character scopes."""
    with pytest.raises(ClientRegistrationError):
        await async_register_dynamic_client(
            hass,
            f"{MCP_SERVER_BASE_URL}/register",
            OAUTH_CALLBACK_URL,
            token_endpoint_auth_methods=["client_secret_post"],
            scopes=scopes,
        )


@pytest.mark.parametrize(
    "scopes",
    [
        pytest.param("read", id="string"),
        pytest.param(["read", 1], id="mixed"),
    ],
)
def test_normalized_scopes_rejects_malformed_scopes(scopes: Any) -> None:
    """Normalizing scopes does not split a string into characters."""
    with pytest.raises(ClientRegistrationError):
        normalized_scopes(scopes)
