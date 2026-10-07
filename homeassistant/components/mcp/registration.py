"""OAuth 2.0 Dynamic Client Registration (RFC 7591) for MCP servers."""

from collections.abc import Mapping
from dataclasses import dataclass
import json
import logging
from typing import Any, cast

import httpx2
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata
from pydantic import AnyUrl, ValidationError
from yarl import URL

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from .const import (
    DCR_CLIENT_NAME,
    DOMAIN,
    SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS,
    TOKEN_ENDPOINT_AUTH_BASIC,
    TOKEN_ENDPOINT_AUTH_NONE,
    TOKEN_ENDPOINT_AUTH_POST,
    TokenEndpointAuthMethod,
)

_REGISTERED_CLIENT_VERSION = 1

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


@dataclass(frozen=True, slots=True)
class RegisteredClientIdentity:
    """OAuth client identity scoped to one authorization server.

    Client ids are only unique per authorization server, so the stored
    credential id includes the server and the auth method.
    """

    authorize_url: str
    token_url: str
    client_id: str
    method: TokenEndpointAuthMethod


def select_token_endpoint_auth_method(
    methods: list[str] | None,
) -> TokenEndpointAuthMethod:
    """Pick a token endpoint auth method the authorization server allows.

    RFC 8414 defaults an omitted token_endpoint_auth_methods_supported to
    client_secret_basic. An explicit list is used as advertised: public
    clients are preferred when listed, otherwise a confidential method Home
    Assistant can present. An explicit list with no supported method is an
    error.
    """
    if methods is None:
        return TOKEN_ENDPOINT_AUTH_BASIC
    for method in SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS:
        if method in methods:
            return method
    raise ClientRegistrationError(
        "Authorization server does not advertise a supported token endpoint auth method"
    )


def encode_registered_client_id(identity: RegisteredClientIdentity) -> str:
    """Return a lossless client id scoped to one authorization server.

    Application credential storage de-duplicates on a slug of
    ``mcp.{client_id}``. Hex keeps that slug reversible, so two servers that
    issue the same client id, or two ids that slugify the same, cannot share
    a secret.
    """
    payload = {
        "authorize_url": identity.authorize_url,
        "client_id": identity.client_id,
        "method": identity.method,
        "token_url": identity.token_url,
        "v": _REGISTERED_CLIENT_VERSION,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode().hex()


def decode_registered_client_id(value: str) -> RegisteredClientIdentity | None:
    """Return the identity stored in a client id.

    Manual application credentials are not encoded and return None.
    """
    try:
        payload = json.loads(bytes.fromhex(value))
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("v") != _REGISTERED_CLIENT_VERSION:
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
        or method not in SUPPORTED_TOKEN_ENDPOINT_AUTH_METHODS
    ):
        return None
    return RegisteredClientIdentity(
        authorize_url=authorize_url,
        token_url=token_url,
        client_id=client_id,
        method=cast(TokenEndpointAuthMethod, method),
    )


def registered_client_auth_domain(encoded_client_id: str) -> str:
    """Return the application credential id for a registered client.

    Deletion refuses a credential whose storage id equals the config entry
    auth_implementation. That storage id is the slug of ``mcp.{client_id}``.
    """
    return slugify(f"{DOMAIN}.{encoded_client_id}")


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

    method = _issued_auth_method(
        payload.get("token_endpoint_auth_method"), requested_method
    )
    try:
        info = OAuthClientInformationFull.model_validate(payload)
    except ValidationError as err:
        # Some servers return a client id without the rest of the metadata.
        _LOGGER.debug("Registration response was only partially valid: %s", err)
        return RegisteredClient(client_id, client_secret, method)

    if not info.client_id:
        raise ClientRegistrationError("Registration response did not include client_id")
    return RegisteredClient(info.client_id, info.client_secret or "", method)


def _issued_auth_method(
    value: Any, requested_method: TokenEndpointAuthMethod
) -> TokenEndpointAuthMethod:
    """Return the auth method from a registration response.

    An omitted or null method keeps the method that was requested. An explicit
    method must be one Home Assistant can present.
    """
    if value is None:
        return requested_method
    if value == TOKEN_ENDPOINT_AUTH_NONE:
        return TOKEN_ENDPOINT_AUTH_NONE
    if value == TOKEN_ENDPOINT_AUTH_POST:
        return TOKEN_ENDPOINT_AUTH_POST
    if value == TOKEN_ENDPOINT_AUTH_BASIC:
        return TOKEN_ENDPOINT_AUTH_BASIC
    raise ClientRegistrationError(
        "Registration response token_endpoint_auth_method is not supported"
    )
