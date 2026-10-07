"""OAuth 2.0 Dynamic Client Registration (RFC 7591) for MCP servers."""

from collections.abc import Mapping
import logging
from typing import Any

import httpx2
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata
from pydantic import AnyUrl, ValidationError
from yarl import URL

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from .const import (
    DCR_AUTH_DOMAIN_PREFIX,
    DCR_CLIENT_NAME,
    SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS,
    TOKEN_ENDPOINT_AUTH_BASIC,
    TOKEN_ENDPOINT_AUTH_NONE,
    TOKEN_ENDPOINT_AUTH_POST,
    TokenEndpointAuthMethod,
)

_LOGGER = logging.getLogger(__name__)


class RegisteredClient:
    """Credentials issued by a dynamic client registration response."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_endpoint_auth_method: TokenEndpointAuthMethod,
    ) -> None:
        """Initialize the registered client."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_endpoint_auth_method = token_endpoint_auth_method


class ClientRegistrationError(HomeAssistantError):
    """Dynamic client registration was rejected or the response was unusable."""


def select_token_endpoint_auth_method(
    methods: list[str] | None,
) -> TokenEndpointAuthMethod:
    """Pick a token endpoint auth method the authorization server allows.

    Public clients are preferred when the server allows them, which matches
    MCP clients that authenticate with PKCE. Otherwise a confidential method
    that Home Assistant can present is used.
    """
    if not methods:
        return TOKEN_ENDPOINT_AUTH_NONE
    for method in SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS:
        if method in methods:
            return method
    return TOKEN_ENDPOINT_AUTH_NONE


def dynamic_client_auth_domain(client_id: str, method: TokenEndpointAuthMethod) -> str:
    """Return the application credential auth domain for a registered client."""
    return f"{DCR_AUTH_DOMAIN_PREFIX}{method}.{slugify(client_id)}"


def token_endpoint_auth_method_from_domain(
    auth_domain: str,
) -> TokenEndpointAuthMethod | None:
    """Return the auth method encoded into a dynamic client auth domain."""
    if not auth_domain.startswith(DCR_AUTH_DOMAIN_PREFIX):
        return None
    method, separator, _slug = auth_domain.removeprefix(
        DCR_AUTH_DOMAIN_PREFIX
    ).partition(".")
    if not separator:
        return None
    return _coerce_auth_method(method, None)


def resolve_registration_endpoint(auth_server_url: str, endpoint: str) -> str:
    """Resolve a registration endpoint against the authorization server URL."""
    parsed = URL(endpoint)
    if parsed.is_absolute():
        return endpoint
    return str(URL(auth_server_url).join(parsed))


async def async_register_dynamic_client(
    registration_endpoint: str,
    redirect_uri: str,
    *,
    token_endpoint_auth_methods: list[str] | None,
    scopes: list[str] | None,
) -> RegisteredClient:
    """Register an OAuth client at the authorization server.

    Transport errors from the HTTP client propagate so the config flow can map
    them the same way as metadata discovery.
    """
    method = select_token_endpoint_auth_method(token_endpoint_auth_methods)
    try:
        metadata = OAuthClientMetadata(
            redirect_uris=[AnyUrl(redirect_uri)],
            token_endpoint_auth_method=method,
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            client_name=DCR_CLIENT_NAME,
            scope=" ".join(scopes) if scopes else None,
        )
    except ValidationError as err:
        raise ClientRegistrationError("Invalid client metadata") from err

    # OIDC defaults an omitted application_type to "web". Home Assistant's
    # redirect URI is a web callback, so send that explicitly.
    payload = metadata.model_dump(mode="json", exclude_none=True)
    payload["application_type"] = "web"

    async with httpx2.AsyncClient() as client:
        response = await client.post(
            registration_endpoint,
            json=payload,
            headers={"Accept": "application/json"},
        )

    if response.status_code not in (200, 201):
        _LOGGER.debug(
            "OAuth client registration at %s failed with status %s",
            registration_endpoint,
            response.status_code,
        )
        raise ClientRegistrationError(
            f"Registration failed with status {response.status_code}"
        )

    try:
        body = response.json()
    except ValueError as err:
        raise ClientRegistrationError("Registration response was not JSON") from err

    return _parse_registration_response(body, redirect_uri, method)


def _parse_registration_response(
    body: Any,
    redirect_uri: str,
    requested_method: TokenEndpointAuthMethod,
) -> RegisteredClient:
    """Parse an RFC 7591 registration response into issued credentials."""
    if not isinstance(body, Mapping):
        raise ClientRegistrationError("Registration response was not an object")

    payload = dict(body)
    if not payload.get("redirect_uris"):
        payload["redirect_uris"] = [redirect_uri]

    client_id = payload.get("client_id")
    client_secret = payload.get("client_secret") or ""
    if not isinstance(client_id, str) or not client_id:
        raise ClientRegistrationError("Registration response did not include client_id")
    if not isinstance(client_secret, str):
        raise ClientRegistrationError("Registration response client_secret was invalid")

    returned_method = payload.get("token_endpoint_auth_method")
    try:
        info = OAuthClientInformationFull.model_validate(payload)
    except ValidationError as err:
        # Some servers return a client id without the rest of the metadata.
        _LOGGER.debug("Registration response was only partially valid: %s", err)
        method = _coerce_auth_method(returned_method, requested_method)
        if method is None:
            method = requested_method
        return RegisteredClient(client_id, client_secret, method)

    if not info.client_id:
        raise ClientRegistrationError("Registration response did not include client_id")
    method = _coerce_auth_method(info.token_endpoint_auth_method, requested_method)
    if method is None:
        method = requested_method
    return RegisteredClient(info.client_id, info.client_secret or "", method)


def _coerce_auth_method(
    value: Any, default: TokenEndpointAuthMethod | None
) -> TokenEndpointAuthMethod | None:
    """Return a supported token endpoint auth method, or the default."""
    if value == TOKEN_ENDPOINT_AUTH_NONE:
        return TOKEN_ENDPOINT_AUTH_NONE
    if value == TOKEN_ENDPOINT_AUTH_POST:
        return TOKEN_ENDPOINT_AUTH_POST
    if value == TOKEN_ENDPOINT_AUTH_BASIC:
        return TOKEN_ENDPOINT_AUTH_BASIC
    return default
