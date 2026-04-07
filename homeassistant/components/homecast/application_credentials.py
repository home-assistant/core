"""OAuth application credentials for Homecast."""

from __future__ import annotations

from contextlib import contextmanager
import contextvars

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

from .const import OAUTH_AUTHORIZE_URL, OAUTH_TOKEN_URL, SCOPES

# Context variable for dynamic OAuth server URLs (community mode).
# Set before calling into AbstractOAuth2FlowHandler so application_credentials
# resolves to the correct server (local community or cloud).
_server_context: contextvars.ContextVar[AuthorizationServer | None] = (
    contextvars.ContextVar("homecast_authorization_server", default=None)
)


@contextmanager
def authorization_server_context(server: AuthorizationServer):
    """Temporarily override the authorization server URLs."""
    token = _server_context.set(server)
    try:
        yield
    finally:
        _server_context.reset(token)


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return the Homecast authorization server.

    Uses the context variable if set (community mode), otherwise cloud defaults.
    """
    if (server := _server_context.get()) is not None:
        return server
    return AuthorizationServer(
        authorize_url=OAUTH_AUTHORIZE_URL,
        token_url=OAUTH_TOKEN_URL,
    )


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> HomecastOAuth2Implementation:
    """Return a custom auth implementation with PKCE."""
    server = _server_context.get()
    authorize_url = server.authorize_url if server else OAUTH_AUTHORIZE_URL
    token_url = server.token_url if server else OAUTH_TOKEN_URL

    return HomecastOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        authorize_url,
        token_url,
        credential.client_secret,
    )


class HomecastOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Homecast OAuth2 implementation with PKCE (S256)."""

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return super().extra_authorize_data | {
            "scope": SCOPES,
        }
