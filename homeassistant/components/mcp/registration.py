"""OAuth dynamic client registration for MCP servers."""

import json
import logging
from typing import Any, cast

from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl, ValidationError
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util import slugify

from .const import (
    DCR_CLIENT_NAME,
    DOMAIN,
    TOKEN_ENDPOINT_AUTH_BASIC,
    TOKEN_ENDPOINT_AUTH_NONE,
    TOKEN_ENDPOINT_AUTH_POST,
    TokenEndpointAuthMethod,
)

_REGISTERED_CLIENT_ID_PREFIX = "mcp-dcr:"
_LOGGER = logging.getLogger(__name__)

_AUTH_METHODS: tuple[TokenEndpointAuthMethod, ...] = (
    TOKEN_ENDPOINT_AUTH_NONE,
    TOKEN_ENDPOINT_AUTH_POST,
    TOKEN_ENDPOINT_AUTH_BASIC,
)


class ClientRegistrationError(HomeAssistantError):
    """Dynamic client registration was rejected or the response was unusable."""


def select_token_endpoint_auth_method(
    methods: list[str] | None,
) -> TokenEndpointAuthMethod:
    """Pick a supported token endpoint auth method.

    RFC 8414 defaults an omitted list to client_secret_basic.
    """
    if methods is None:
        return TOKEN_ENDPOINT_AUTH_BASIC
    for method in _AUTH_METHODS:
        if method in methods:
            return method
    raise ClientRegistrationError(
        "Authorization server does not advertise a supported token endpoint auth method"
    )


def encode_registered_client_id(
    authorize_url: str,
    token_url: str,
    client_id: str,
    method: TokenEndpointAuthMethod,
) -> str:
    """Return a client id scoped to one authorization server.

    Storage de-duplicates on a slug of the client id. The prefix keeps a
    manual client id from being treated as a registered client.
    """
    payload = json.dumps(
        {
            "authorize_url": authorize_url,
            "client_id": client_id,
            "method": method,
            "token_url": token_url,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{_REGISTERED_CLIENT_ID_PREFIX}{payload.encode().hex()}"


def decode_registered_client_id(
    value: str,
) -> tuple[str, str, str, TokenEndpointAuthMethod] | None:
    """Return authorize URL, token URL, client id, and auth method."""
    if not value.startswith(_REGISTERED_CLIENT_ID_PREFIX):
        return None
    try:
        payload = json.loads(
            bytes.fromhex(value.removeprefix(_REGISTERED_CLIENT_ID_PREFIX))
        )
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    authorize_url = payload.get("authorize_url")
    token_url = payload.get("token_url")
    client_id = payload.get("client_id")
    method = payload.get("method")
    if (
        not isinstance(authorize_url, str)
        or not authorize_url
        or not isinstance(token_url, str)
        or not token_url
        or not isinstance(client_id, str)
        or not client_id
        or method not in _AUTH_METHODS
    ):
        return None
    return authorize_url, token_url, client_id, cast(TokenEndpointAuthMethod, method)


def registered_client_auth_domain(encoded_client_id: str) -> str:
    """Return the storage id for a registered client.

    Deletion refuses a credential whose id equals the config entry
    auth_implementation.
    """
    return slugify(f"{DOMAIN}.{encoded_client_id}")


def resolve_registration_endpoint(auth_server_url: str, endpoint: str) -> str:
    """Resolve a registration endpoint against the authorization server URL."""
    parsed = URL(endpoint)
    if parsed.is_absolute():
        return endpoint
    return str(URL(auth_server_url).join(parsed))


def _scope_value(scopes: Any) -> str | None:
    """Return a scope string when scopes are a list of strings."""
    if isinstance(scopes, list) and all(isinstance(scope, str) for scope in scopes):
        return " ".join(scopes) or None
    return None


async def async_register_dynamic_client(
    hass: HomeAssistant,
    registration_endpoint: str,
    redirect_uri: str,
    *,
    token_endpoint_auth_methods: list[str] | None,
    scopes: Any,
) -> tuple[str, str, TokenEndpointAuthMethod]:
    """Register at the advertised endpoint and return the issued client.

    The MCP SDK helper falls back to ``/register`` when no endpoint is
    advertised, so this posts only to the endpoint the server published.
    The response body is not logged.
    """
    method = select_token_endpoint_auth_method(token_endpoint_auth_methods)
    try:
        metadata = OAuthClientMetadata(
            redirect_uris=[AnyUrl(redirect_uri)],
            token_endpoint_auth_method=method,
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            client_name=DCR_CLIENT_NAME,
            scope=_scope_value(scopes),
        )
    except ValidationError:
        # ValidationError includes the submitted metadata.
        raise ClientRegistrationError("Invalid client metadata") from None

    payload = metadata.model_dump(mode="json", exclude_none=True)
    payload["application_type"] = "web"
    client = get_async_client(hass)
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
    except ValueError:
        # The parser error can echo the body, which may contain a secret.
        raise ClientRegistrationError("Registration response was not JSON") from None
    return _issued_client(body, redirect_uri, method)


def _issued_client(
    body: Any, redirect_uri: str, requested_method: TokenEndpointAuthMethod
) -> tuple[str, str, TokenEndpointAuthMethod]:
    """Return client id, secret, and auth method from a registration response."""
    if not isinstance(body, dict):
        raise ClientRegistrationError("Registration response was not an object")
    client_id = body.get("client_id")
    if not isinstance(client_id, str) or not client_id:
        raise ClientRegistrationError("Registration response did not include client_id")

    method = body.get("token_endpoint_auth_method", requested_method)
    if method not in _AUTH_METHODS:
        raise ClientRegistrationError(
            "Registration response token_endpoint_auth_method is not supported"
        )
    method = cast(TokenEndpointAuthMethod, method)

    if method == TOKEN_ENDPOINT_AUTH_NONE:
        # A public client must not keep or send a secret, even if one was echoed.
        client_secret = ""
    else:
        secret = body.get("client_secret")
        if not isinstance(secret, str) or not secret:
            raise ClientRegistrationError(
                "Registration response did not include client_secret"
            )
        client_secret = secret

    if "redirect_uris" in body and (
        not isinstance(body["redirect_uris"], list)
        or redirect_uri not in body["redirect_uris"]
    ):
        raise ClientRegistrationError(
            "Registration response did not include the redirect URI"
        )
    return client_id, client_secret, method
