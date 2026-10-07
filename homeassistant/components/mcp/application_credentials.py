"""Application credentials platform for Model Context Protocol."""

from base64 import b64encode
from collections.abc import Generator
from contextlib import contextmanager
import contextvars
from typing import cast, override
from urllib.parse import quote_plus

from aiohttp import ClientError, ClientResponseError

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthImplementationNotApplicable,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2ImplementationWithPkce,
    _raise_mapped_token_error,
)

from .const import DCR_CLIENT_NAME, TOKEN_ENDPOINT_AUTH_BASIC, TOKEN_ENDPOINT_AUTH_NONE
from .registration import decode_registered_client_id

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


async def async_get_authorization_server(_hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server, for the default auth implementation."""
    return _mcp_context.get()


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return the OAuth implementation for stored MCP credentials.

    Registered clients use PKCE. Manual credentials keep the previous
    implementation.
    """
    authorization_server = await async_get_authorization_server(hass)
    if (identity := decode_registered_client_id(credential.client_id)) is None:
        return AuthImplementation(hass, auth_domain, credential, authorization_server)
    authorize_url, token_url, client_id, method = identity
    if (
        authorize_url != authorization_server.authorize_url
        or token_url != authorization_server.token_url
    ):
        raise AuthImplementationNotApplicable
    return McpRegisteredOAuth2Implementation(
        hass,
        auth_domain,
        client_id,
        authorization_server.authorize_url,
        authorization_server.token_url,
        credential.client_secret,
        token_endpoint_auth_method=method,
    )


def _encode_client_basic_auth(client_id: str, client_secret: str) -> str:
    """Return RFC 6749 HTTP Basic credentials for a confidential client."""
    username = quote_plus(client_id)
    password = quote_plus(client_secret)
    return b64encode(f"{username}:{password}".encode()).decode("ascii")


class McpRegisteredOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """OAuth implementation for a dynamically registered MCP client."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_id: str,
        authorize_url: str,
        token_url: str,
        client_secret: str,
        token_endpoint_auth_method: str,
    ) -> None:
        """Initialize the implementation."""
        if token_endpoint_auth_method == TOKEN_ENDPOINT_AUTH_NONE:
            client_secret = ""
        super().__init__(
            hass,
            domain,
            client_id,
            authorize_url,
            token_url,
            client_secret,
        )
        self.token_endpoint_auth_method = token_endpoint_auth_method

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return DCR_CLIENT_NAME

    @override
    async def _token_request(self, data: dict) -> dict:
        """Request a token.

        client_secret_basic uses the Authorization header. Other methods use
        the local OAuth helper.
        """
        if self.token_endpoint_auth_method != TOKEN_ENDPOINT_AUTH_BASIC:
            return await super()._token_request(data)

        session = async_get_clientsession(self.hass)
        body = {
            key: value
            for key, value in data.items()
            if key not in ("client_id", "client_secret")
        }
        body["client_id"] = self.client_id
        headers = {
            "Authorization": "Basic "
            + _encode_client_basic_auth(self.client_id, self.client_secret)
        }
        try:
            resp = await session.post(self.token_url, data=body, headers=headers)
            resp.raise_for_status()
            return cast(dict, await resp.json())
        except ClientResponseError as err:
            _raise_mapped_token_error(err, self.service_domain)
        except ClientError as err:
            _raise_mapped_token_error(err, self.service_domain)
