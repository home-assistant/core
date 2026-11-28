"""Application credentials platform for Model Context Protocol."""

from collections.abc import Generator
from contextlib import contextmanager
import contextvars
from dataclasses import dataclass
from typing import override

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

from .auth import canonical_resource_uri


@dataclass(frozen=True)
class MCPAuthContext:
    """Context for MCP OAuth2 authorization."""

    authorization_server: AuthorizationServer
    resource: str


_mcp_context: contextvars.ContextVar[MCPAuthContext | None] = contextvars.ContextVar(
    "mcp_authorization_server_context",
    default=None,
)


@contextmanager
def authorization_server_context(
    authorization_server: AuthorizationServer,
    resource: str,
) -> Generator[None]:
    """Context manager for setting the active authorization server and resource."""
    token = _mcp_context.set(MCPAuthContext(authorization_server, resource))
    try:
        yield
    finally:
        _mcp_context.reset(token)


class MCPOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """MCP OAuth2 implementation with PKCE and RFC 8707 resource indicator."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        authorize_url: str,
        token_url: str,
        resource: str,
        client_secret: str = "",
        name: str | None = None,
    ) -> None:
        """Initialize MCPOAuth2Implementation."""
        super().__init__(
            hass,
            domain,
            client_id,
            authorize_url,
            token_url,
            client_secret,
        )
        self._name = name
        self._resource = canonical_resource_uri(resource)

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return self._name or self.client_id

    @property
    @override
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            **super().extra_authorize_data,
            "resource": self._resource,
        }

    @override
    async def _token_request(self, data: dict) -> dict:
        """Make a token request including the RFC 8707 resource parameter."""
        return await super()._token_request({**data, "resource": self._resource})


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> MCPOAuth2Implementation:
    """Return OAuth2 implementation for the active MCP authorization server."""
    if (context := _mcp_context.get()) is None:
        raise RuntimeError("No MCP authorization server set in context")
    return MCPOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        context.authorization_server.authorize_url,
        context.authorization_server.token_url,
        context.resource,
        credential.client_secret,
        credential.name,
    )
