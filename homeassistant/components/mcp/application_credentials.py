"""Application credentials platform for Model Context Protocol."""

from base64 import b64encode
from collections.abc import Generator
from contextlib import contextmanager
import contextvars
import json
import logging
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

_LOGGER = logging.getLogger(__name__)

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
    """Return authorization server, for the default auth implementation."""
    if _mcp_context.get() is None:
        raise RuntimeError("No MCP authorization server set in context")
    return _mcp_context.get()


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return the OAuth implementation for stored MCP credentials.

    Dynamically registered clients use PKCE. The MCP authorization spec requires
    it, and public clients have no secret to authenticate the token request.
    Pre-registered application credentials keep the previous implementation so
    servers that only support those clients are unchanged.
    """
    authorization_server = await async_get_authorization_server(hass)
    # Manual credentials store the OAuth client id directly. Registered
    # clients store a server-scoped encoding so the same client id can be
    # issued by more than one authorization server.
    if (identity := decode_registered_client_id(credential.client_id)) is None:
        return AuthImplementation(hass, auth_domain, credential, authorization_server)
    # A client issued by another authorization server must not be offered
    # under this server's authorize and token URLs.
    if (
        identity.authorize_url != authorization_server.authorize_url
        or identity.token_url != authorization_server.token_url
    ):
        raise AuthImplementationNotApplicable
    return McpRegisteredOAuth2Implementation(
        hass,
        auth_domain,
        identity.client_id,
        authorization_server.authorize_url,
        authorization_server.token_url,
        credential.client_secret,
        token_endpoint_auth_method=identity.method,
        registered_redirect_uri=identity.redirect_uri,
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
        *,
        registered_redirect_uri: str | None = None,
    ) -> None:
        """Initialize the implementation."""
        # A public client authenticates with PKCE only. Ignore a secret the
        # server may have echoed so it is not sent on the token request.
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
        self._registered_redirect_uri = registered_redirect_uri

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return DCR_CLIENT_NAME

    @property
    @override
    def redirect_uri(self) -> str:
        """Return the callback this client was registered with.

        The authorization server rejects a callback that was not registered.
        Reauth keeps using the stored callback when the external URL changes.
        A client stored before the callback was recorded uses the current URL.
        """
        if self._registered_redirect_uri is not None:
            return self._registered_redirect_uri
        return super().redirect_uri

    @override
    async def _token_request(self, data: dict) -> dict:
        """Request a token.

        client_secret_basic clients authenticate with the Authorization header.
        Public clients and client_secret_post clients use the local OAuth helper.
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

        _LOGGER.debug("Sending token request to %s", self.token_url)

        try:
            resp = await session.post(self.token_url, data=body, headers=headers)
            if resp.status >= 400:
                error_body = ""
                try:
                    error_body = await resp.text()
                    error_data = json.loads(error_body)
                    error_code = error_data.get("error", "unknown error")
                    error_description = error_data.get("error_description")
                    detail = (
                        f"{error_code}: {error_description}"
                        if error_description
                        else error_code
                    )
                except ClientError, ValueError, AttributeError:
                    detail = error_body[:200] if error_body else "unknown error"
                _LOGGER.debug(
                    "Token request for %s failed (%s): %s",
                    self.domain,
                    resp.status,
                    detail,
                )
            resp.raise_for_status()
            return cast(dict, await resp.json())
        except ClientResponseError as err:
            _raise_mapped_token_error(err, self.service_domain)
        except ClientError as err:
            _raise_mapped_token_error(err, self.service_domain)
