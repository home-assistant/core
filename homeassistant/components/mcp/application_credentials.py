"""Application credentials platform for Model Context Protocol."""

from collections.abc import Generator
from contextlib import contextmanager
import contextvars
from typing import override

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

CONF_ACTIVE_AUTHORIZATION_SERVER = "active_authorization_server"

_mcp_context: contextvars.ContextVar[AuthorizationServer] = contextvars.ContextVar(
    "mcp_authorization_server_context"
)


@contextmanager
def authorization_server_context(
    authorization_server: AuthorizationServer,
) -> Generator[None]:
    """Context manager for setting the active authorization server."""
    token = _mcp_context.set(authorization_server)
    try:
        yield
    finally:
        _mcp_context.reset(token)


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return the active authorization server."""
    authorization_server = _mcp_context.get(None)
    if authorization_server is None:
        raise RuntimeError("No MCP authorization server set in context")
    return authorization_server


class MCPAuthImplementation(config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce):
    """OAuth2 implementation for MCP servers, with PKCE required by the MCP OAuth profile."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth_domain: str,
        credential: ClientCredential,
        authorization_server: AuthorizationServer,
    ) -> None:
        """Initialize MCPAuthImplementation."""
        super().__init__(
            hass,
            auth_domain,
            credential.client_id,
            authorization_server.authorize_url,
            authorization_server.token_url,
            client_secret=credential.client_secret,
        )
        self._name = credential.name

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return self._name or self.client_id


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return an MCP-spec OAuth2 implementation with PKCE enabled.

    The MCP OAuth 2.1 profile mandates PKCE S256 on the authorization
    code flow. The default `application_credentials.AuthImplementation`
    extends `LocalOAuth2Implementation` (no PKCE), so spec-strict MCP
    servers reject authorize requests with `invalid_request: code_challenge`.
    Override here so the `mcp` integration always uses
    `LocalOAuth2ImplementationWithPkce`.
    """
    authorization_server = await async_get_authorization_server(hass)
    return MCPAuthImplementation(hass, auth_domain, credential, authorization_server)
