"""Application credentials platform for Model Context Protocol."""

from collections.abc import Generator
from contextlib import contextmanager
import contextvars
from typing import override

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    MY_AUTH_CALLBACK_PATH,
    LocalOAuth2ImplementationWithPkce,
)

from .const import CIMD_AUTH_IMPLEMENTATION, CIMD_CLIENT_ID, DOMAIN

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


async def async_get_authorization_server(
    _hass: HomeAssistant,
) -> AuthorizationServer:
    """Return authorization server, for the default auth implementation."""
    return _mcp_context.get()


class McpClientMetadataImplementation(LocalOAuth2ImplementationWithPkce):
    """Public client identified by Home Assistant's client ID metadata URL."""

    def __init__(
        self,
        hass: HomeAssistant,
        authorize_url: str,
        token_url: str,
        resource: str,
    ) -> None:
        """Initialize the PKCE client. No client secret is stored."""
        super().__init__(
            hass,
            CIMD_AUTH_IMPLEMENTATION,
            CIMD_CLIENT_ID,
            authorize_url,
            token_url,
        )
        self.resource = resource

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return "Home Assistant"

    @property
    @override
    def redirect_uri(self) -> str:
        """Return the redirect URI published in the client metadata."""
        return MY_AUTH_CALLBACK_PATH

    @property
    @override
    def service_domain(self) -> str:
        """Domain of the service the tokens are for."""
        return DOMAIN

    @property
    @override
    def extra_authorize_data(self) -> dict:
        """PKCE parameters plus the MCP server resource."""
        return {
            "resource": self.resource,
            **super().extra_authorize_data,
        }

    @override
    async def _token_request(self, data: dict) -> dict:
        """Include the MCP server resource in token requests."""
        data["resource"] = self.resource
        return await super()._token_request(data)
