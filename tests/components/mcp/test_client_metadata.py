"""Tests for MCP OAuth client ID metadata documents."""

from typing import Any
from unittest.mock import Mock

import httpx2
import pytest
import respx
from yarl import URL

from homeassistant.components.mcp import async_get_config_entry_implementation
from homeassistant.components.mcp.application_credentials import (
    McpClientMetadataImplementation,
)
from homeassistant.components.mcp.const import (
    CIMD_AUTH_IMPLEMENTATION,
    CIMD_CLIENT_ID,
    CONF_AUTHORIZATION_URL,
    CONF_SCOPE,
    CONF_TOKEN_URL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.config_entry_oauth2_flow import (
    MY_AUTH_CALLBACK_PATH,
    _encode_jwt,
)

from .conftest import (
    MCP_SERVER_URL,
    OAUTH_AUTHORIZE_URL,
    OAUTH_TOKEN_URL,
    TEST_API_NAME,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

OAUTH_DISCOVERY_ENDPOINT = (
    "http://1.1.1.1:8080/.well-known/oauth-authorization-server/mcp"
)
CALLBACK_PATH = "/auth/external/callback"
OAUTH_TOKEN_PAYLOAD = {
    "refresh_token": "mock-refresh-token",
    "access_token": "mock-access-token",
    "type": "Bearer",
    "expires_in": 60,
}


def _metadata(**extra: Any) -> dict[str, Any]:
    """Return authorization server metadata."""
    metadata: dict[str, Any] = {
        "authorization_endpoint": OAUTH_AUTHORIZE_URL,
        "token_endpoint": OAUTH_TOKEN_URL,
        "scopes_supported": ["read", "write"],
    }
    metadata.update(extra)
    return metadata


async def _start(
    hass: HomeAssistant, mock_mcp_client: Mock, metadata: dict[str, Any]
) -> dict[str, Any]:
    """Run user setup until OAuth discovery finishes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_mcp_client.side_effect = httpx2.HTTPStatusError(
        "Authentication required", request=None, response=httpx2.Response(401)
    )
    respx.get(OAUTH_DISCOVERY_ENDPOINT).mock(
        return_value=httpx2.Response(200, json=metadata)
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: MCP_SERVER_URL}
    )


def test_client_metadata_constants() -> None:
    """The published client id is the URL that serves the metadata document."""
    assert CIMD_CLIENT_ID == "https://www.home-assistant.io/mcp/oauth-client.json"
    assert CIMD_AUTH_IMPLEMENTATION == "mcp_client_metadata"


@respx.mock
@pytest.mark.usefixtures("mock_setup_entry")
async def test_client_metadata_document_creates_an_entry(
    hass: HomeAssistant,
    mock_mcp_client: Mock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """A server that supports client id metadata skips application credentials."""
    result = await _start(
        hass,
        mock_mcp_client,
        _metadata(client_id_metadata_document_supported=True),
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    query = URL(result["url"]).query
    assert query["client_id"] == CIMD_CLIENT_ID
    assert query["redirect_uri"] == MY_AUTH_CALLBACK_PATH
    assert query["code_challenge_method"] == "S256"
    assert query["code_challenge"]
    assert query["resource"] == MCP_SERVER_URL
    assert query["scope"] == "read write"
    assert "POST" not in [call.request.method for call in respx.calls]

    state = _encode_jwt(
        hass,
        {"flow_id": result["flow_id"], "redirect_uri": MY_AUTH_CALLBACK_PATH},
    )
    client = await hass_client_no_auth()
    response = await client.get(f"{CALLBACK_PATH}?code=abcd&state={state}")
    assert response.status == 200

    aioclient_mock.post(OAUTH_TOKEN_URL, json=OAUTH_TOKEN_PAYLOAD)
    mock_mcp_client.side_effect = None
    initialized = Mock()
    initialized.serverInfo.name = TEST_API_NAME
    mock_mcp_client.return_value.initialize.return_value = initialized
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_API_NAME
    assert result["data"]["auth_implementation"] == CIMD_AUTH_IMPLEMENTATION
    assert result["data"][CONF_URL] == MCP_SERVER_URL
    assert result["data"][CONF_SCOPE] == ["read", "write"]
    result["data"].pop(CONF_TOKEN)

    _method, _url, body, _headers = aioclient_mock.mock_calls[0]
    assert body["client_id"] == CIMD_CLIENT_ID
    assert body["resource"] == MCP_SERVER_URL
    assert "code_verifier" in body
    assert "client_secret" not in body


@pytest.mark.parametrize(
    "supported",
    [False, "true", 1, None],
)
@respx.mock
async def test_client_metadata_is_not_used_unless_explicitly_supported(
    hass: HomeAssistant, mock_mcp_client: Mock, supported: Any
) -> None:
    """Only a JSON true enables the published client id."""
    result = await _start(
        hass,
        mock_mcp_client,
        _metadata(client_id_metadata_document_supported=supported),
    )
    assert result["reason"] == "missing_credentials"


@respx.mock
async def test_existing_credential_is_preferred(
    hass: HomeAssistant, mock_mcp_client: Mock, credential: None
) -> None:
    """A stored application credential is used before the metadata client."""
    result = await _start(
        hass,
        mock_mcp_client,
        _metadata(client_id_metadata_document_supported=True),
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "credentials_choice"


async def test_client_metadata_entry_reuses_the_published_client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Token refresh for a metadata entry uses the same public client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": CIMD_AUTH_IMPLEMENTATION,
            CONF_AUTHORIZATION_URL: OAUTH_AUTHORIZE_URL,
            CONF_TOKEN_URL: OAUTH_TOKEN_URL,
            CONF_URL: MCP_SERVER_URL,
        },
    )
    entry.add_to_hass(hass)
    implementation = await async_get_config_entry_implementation(hass, entry)
    assert isinstance(implementation, McpClientMetadataImplementation)
    assert implementation.client_id == CIMD_CLIENT_ID
    assert implementation.client_secret == ""
    assert implementation.redirect_uri == MY_AUTH_CALLBACK_PATH
    assert implementation.name == "Home Assistant"
    assert implementation.service_domain == DOMAIN

    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": "refreshed",
            "refresh_token": "next",
            "expires_in": 60,
        },
    )
    token = await implementation.async_refresh_token(
        {"access_token": "old", "refresh_token": "refresh", "expires_in": 1}
    )
    assert token["access_token"] == "refreshed"
    _method, _url, body, _headers = aioclient_mock.mock_calls[0]
    assert body["client_id"] == CIMD_CLIENT_ID
    assert body["resource"] == MCP_SERVER_URL
    assert body["grant_type"] == "refresh_token"
    assert "client_secret" not in body
