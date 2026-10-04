"""Test MCP discovery and authorization with a CIMD and PKCE client."""

import asyncio
from dataclasses import dataclass
from http import HTTPStatus
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient
import httpx
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from pydantic import AnyUrl
import pytest
from yarl import URL

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import llm

from tests.common import MockConfigEntry
from tests.components.auth import async_setup_auth
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

ISSUER = "https://example.com"
MCP_URL = f"{ISSUER}/api/mcp"
TEST_API_ID = "test-auth"


@dataclass
class MemoryTokenStorage:
    """Store the MCP client's OAuth state for a single connection."""

    tokens: OAuthToken | None = None
    client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        """Return saved tokens."""
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Save tokens."""
        self.tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Return the registered client."""
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Save the registered client."""
        self.client_info = client_info


class AuthTestAPI(llm.API):
    """Expose the authenticated user in an MCP prompt."""

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return an API instance bound to the authenticated request."""
        return llm.APIInstance(
            api=self,
            api_prompt=f"Authenticated user: {llm_context.context.user_id}",
            llm_context=llm_context,
            tools=[],
        )


@pytest.mark.usefixtures("current_request_with_host", "socket_enabled")
@pytest.mark.parametrize("llm_hass_api", [[TEST_API_ID]])
async def test_cimd_pkce_mcp_authorization(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Discover, authorize, and use MCP with public client metadata."""
    client_id = "https://client.example/oauth/client.json"
    redirect_uri = "https://callback.example/oauth/callback"
    await async_process_ha_core_config(hass, {"external_url": ISSUER})
    llm.async_register_api(
        hass, AuthTestAPI(hass=hass, id=TEST_API_ID, name="Auth test")
    )

    async def create_client(app: web.Application) -> TestClient:
        """Set up MCP before starting the HTTP server."""
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.LOADED
        return await aiohttp_client(app)

    client = await async_setup_auth(hass, create_client)
    response = await client.post("/api/mcp")
    assert response.status == HTTPStatus.UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == (
        f'Bearer resource_metadata="{ISSUER}/.well-known/oauth-protected-resource"'
    )

    response = await client.get("/.well-known/oauth-protected-resource")
    resource_metadata = await response.json()
    assert resource_metadata["resource"] == ISSUER
    assert resource_metadata["authorization_servers"] == [ISSUER]

    response = await client.get("/.well-known/oauth-authorization-server")
    server_metadata = await response.json()
    assert server_metadata["code_challenge_methods_supported"] == ["S256"]
    assert server_metadata["client_id_metadata_document_supported"] is True
    assert server_metadata["issuer"] == ISSUER

    client_document = AiohttpClientMocker()
    client_document.get(
        client_id,
        json={
            "client_id": client_id,
            "client_name": "Example client",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
        headers={"Content-Type": "application/json"},
    )
    callback_result: tuple[str, str] | None = None

    async def authorize(authorization_url: str) -> None:
        """Complete the same login API flow used by the authorization page."""
        nonlocal callback_result
        url = URL(authorization_url)
        assert str(url.with_query(None)) == server_metadata["authorization_endpoint"]
        assert url.query["client_id"] == client_id
        assert url.query["redirect_uri"] == redirect_uri
        assert url.query["code_challenge_method"] == "S256"
        assert url.query["resource"].rstrip("/") == ISSUER
        assert url.query["state"]

        response = await client.post(
            "/auth/login_flow",
            json={**url.query, "handler": ["insecure_example", None]},
        )
        assert response.status == HTTPStatus.OK
        flow = await response.json()
        with patch(
            "aiohttp.ClientSession",
            side_effect=lambda *args, **kwargs: client_document.create_session(
                asyncio.get_running_loop()
            ),
        ):
            response = await client.post(
                f"/auth/login_flow/{flow['flow_id']}",
                json={
                    "client_id": client_id,
                    "username": "test-user",
                    "password": "test-pass",
                },
            )
        assert response.status == HTTPStatus.OK
        result = await response.json()
        callback_result = (result["result"], url.query["state"])

    async def get_callback() -> tuple[str, str]:
        """Return the authorization response to the MCP client."""
        assert callback_result is not None
        return callback_result

    async def send_to_hass(request: httpx.Request) -> httpx.Response:
        """Route the SDK's public HTTPS requests to the local test server."""
        assert str(request.url).startswith(f"{ISSUER}/")
        response = await client.request(
            request.method,
            request.url.raw_path.decode(),
            data=await request.aread(),
            headers=dict(request.headers),
        )
        return httpx.Response(
            response.status,
            headers=dict(response.headers),
            content=await response.read(),
        )

    storage = MemoryTokenStorage()
    oauth = OAuthClientProvider(
        server_url=MCP_URL,
        client_metadata=OAuthClientMetadata(
            client_name="Example client",
            redirect_uris=[AnyUrl(redirect_uri)],
            token_endpoint_auth_method="none",
        ),
        client_metadata_url=client_id,
        storage=storage,
        redirect_handler=authorize,
        callback_handler=get_callback,
    )

    async with (
        httpx.AsyncClient(
            auth=oauth, transport=httpx.MockTransport(send_to_hass)
        ) as http,
        streamable_http_client(MCP_URL, http_client=http) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        initialized = await session.initialize()
        assert initialized.serverInfo.name == "home-assistant"
        assert storage.tokens is not None
        refresh_token = hass.auth.async_validate_access_token(
            storage.tokens.access_token
        )
        assert refresh_token is not None
        assert refresh_token.client_id == client_id
        assert refresh_token.resource == ISSUER
        prompt = await session.get_prompt("Auth test")
        assert prompt.messages[0].content.type == "text"
        assert prompt.messages[0].content.text == (
            f"Authenticated user: {refresh_token.user.id}"
        )

    assert client_document.call_count == 1
