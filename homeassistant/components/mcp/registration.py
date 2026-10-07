"""OAuth 2.0 Dynamic Client Registration (RFC 7591) for MCP servers."""

from collections.abc import Mapping
from dataclasses import dataclass
import json
import logging
from typing import Any, cast

from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata
from pydantic import AnyUrl, ValidationError
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client
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
# A manual client id may itself be hex-encoded JSON. Only values with this
# marker are decoded, so that id is not replaced by an embedded one.
_REGISTERED_CLIENT_ID_PREFIX = "mcp-dcr:"
_OMITTED = object()

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


class ClientSecretExpiresError(ClientRegistrationError):
    """The authorization server issued a client secret with a finite lifetime."""


@dataclass(frozen=True, slots=True)
class RegisteredClientIdentity:
    """OAuth client identity scoped to one authorization server.

    Client ids are only unique per authorization server, so the stored
    credential id includes the server, the auth method, and the redirect URI
    and scopes that registration bound to the client. Missing redirect or
    scopes means a previously stored client whose metadata was not recorded.
    """

    authorize_url: str
    token_url: str
    client_id: str
    method: TokenEndpointAuthMethod
    redirect_uri: str | None = None
    scopes: tuple[str, ...] | None = None


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


def _scope_list(scopes: Any) -> list[str] | None:
    """Return scopes when they are a list of strings.

    Omitted scopes request nothing. A string must not be joined, because that
    requests one scope per character. A mixed list cannot be joined either.
    """
    if scopes is None:
        return None
    if isinstance(scopes, list) and all(isinstance(scope, str) for scope in scopes):
        return scopes
    raise ClientRegistrationError("OAuth scopes were not a list of strings")


def normalized_scopes(scopes: list[str] | None) -> tuple[str, ...]:
    """Return scopes as a sorted unique tuple.

    An omitted scope list and an empty list are the same request: no scope.
    """
    if not (scope_list := _scope_list(scopes)):
        return ()
    return tuple(sorted(set(scope_list)))


def registered_client_matches_request(
    identity: RegisteredClientIdentity,
    *,
    authorize_url: str,
    token_url: str,
    redirect_uri: str,
    scopes: tuple[str, ...],
) -> bool:
    """Return whether a stored client was registered for this request.

    RFC 7591 binds redirect URIs and scope to the client. Another MCP resource
    can share the authorization endpoints while using a different callback or
    scope set, so those clients are not interchangeable.
    """
    return (
        identity.authorize_url == authorize_url
        and identity.token_url == token_url
        and identity.redirect_uri == redirect_uri
        and identity.scopes is not None
        and set(identity.scopes) == set(scopes)
    )


def encode_registered_client_id(identity: RegisteredClientIdentity) -> str:
    """Return a lossless client id scoped to one authorization server.

    Application credential storage de-duplicates on a slug of
    ``mcp.{client_id}``. Hex keeps that slug reversible, so two servers that
    issue the same client id, or two ids that slugify the same, cannot share
    a secret. The marker prefix keeps a manual client id from being decoded.
    """
    payload: dict[str, Any] = {
        "authorize_url": identity.authorize_url,
        "client_id": identity.client_id,
        "method": identity.method,
        "token_url": identity.token_url,
        "v": _REGISTERED_CLIENT_VERSION,
    }
    if identity.redirect_uri is not None:
        payload["redirect_uri"] = identity.redirect_uri
    if identity.scopes is not None:
        payload["scopes"] = list(identity.scopes)
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode().hex()
    return f"{_REGISTERED_CLIENT_ID_PREFIX}{encoded}"


def decode_registered_client_id(value: str) -> RegisteredClientIdentity | None:
    """Return the identity stored in a client id.

    Manual application credentials are not encoded and return None. A value
    without the registration marker is left as a manual client id, even when
    the remainder is hex-encoded JSON.
    """
    if not value.startswith(_REGISTERED_CLIENT_ID_PREFIX):
        return None
    try:
        payload = json.loads(
            bytes.fromhex(value.removeprefix(_REGISTERED_CLIENT_ID_PREFIX))
        )
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
    redirect_uri = payload.get("redirect_uri")
    if redirect_uri is not None and (
        not isinstance(redirect_uri, str) or not redirect_uri
    ):
        return None
    if "scopes" not in payload or payload["scopes"] is None:
        scopes = None
    elif isinstance(payload["scopes"], list) and all(
        isinstance(scope, str) for scope in payload["scopes"]
    ):
        scopes = tuple(payload["scopes"])
    else:
        return None
    return RegisteredClientIdentity(
        authorize_url=authorize_url,
        token_url=token_url,
        client_id=client_id,
        method=cast(TokenEndpointAuthMethod, method),
        redirect_uri=redirect_uri,
        scopes=scopes,
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
    hass: HomeAssistant,
    registration_endpoint: str,
    redirect_uri: str,
    *,
    token_endpoint_auth_methods: list[str] | None,
    scopes: list[str] | None,
) -> RegisteredClient:
    """Register an OAuth client at the authorization server.

    The MCP SDK registration request falls back to ``/register`` when metadata
    omits an endpoint, and its response parser rejects a client id returned
    without the rest of the metadata. This posts only to the advertised
    endpoint and still accepts that partial response. The request metadata
    itself is the SDK model.
    Transport errors from the HTTP client propagate so the config flow can map
    them the same way as metadata discovery.
    """
    method = select_token_endpoint_auth_method(token_endpoint_auth_methods)
    scope_list = _scope_list(scopes)
    try:
        metadata = OAuthClientMetadata(
            redirect_uris=[AnyUrl(redirect_uri)],
            token_endpoint_auth_method=method,
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            client_name=DCR_CLIENT_NAME,
            scope=" ".join(scope_list) if scope_list else None,
        )
    except ValidationError as err:
        raise ClientRegistrationError("Invalid client metadata") from err

    # OIDC defaults an omitted application_type to "web". Home Assistant's
    # redirect URI is a web callback, so send that explicitly.
    payload = metadata.model_dump(mode="json", exclude_none=True)
    payload["application_type"] = "web"

    # The default client loads the CA bundle from disk on the event loop.
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
    except ValueError as err:
        raise ClientRegistrationError("Registration response was not JSON") from err

    return _parse_registration_response(
        body, redirect_uri, method, normalized_scopes(scope_list)
    )


def _parse_registration_response(
    body: Any,
    redirect_uri: str,
    requested_method: TokenEndpointAuthMethod,
    requested_scopes: tuple[str, ...],
) -> RegisteredClient:
    """Parse an RFC 7591 registration response into issued credentials."""
    if not isinstance(body, Mapping):
        raise ClientRegistrationError("Registration response was not an object")

    payload = dict(body)
    redirect_uris = _field_or_omitted(payload, "redirect_uris")
    _require_registered_redirect_uri(redirect_uris, redirect_uri)
    if redirect_uris is _OMITTED:
        payload["redirect_uris"] = [redirect_uri]
    _require_granted_scopes(_field_or_omitted(payload, "scope"), requested_scopes)
    _require_authorization_code_grants(payload)

    client_id = payload.get("client_id")
    if not isinstance(client_id, str) or not client_id:
        raise ClientRegistrationError("Registration response did not include client_id")

    method = _issued_auth_method(
        payload.get("token_endpoint_auth_method"), requested_method
    )
    client_secret = _client_secret_from_response(payload.get("client_secret"), method)
    # Application credential storage strips surrounding whitespace. These
    # values are opaque, so a stripped copy would not match the issued one.
    if client_id != client_id.strip() or client_secret != client_secret.strip():
        raise ClientRegistrationError(
            "Registration response client id or secret has surrounding whitespace"
        )
    # Application credentials are not rotated. A finite secret lifetime would
    # leave refresh and reauth on a credential that can no longer be replaced.
    # Public clients never send the secret, so an echoed expiry is ignored.
    _reject_expiring_client_secret(payload.get("client_secret_expires_at"), method)
    try:
        # Some servers return a client id without the rest of the metadata.
        OAuthClientInformationFull.model_validate(payload)
    except ValidationError as err:
        # Log locations and types only. The error string includes input values,
        # and a missing field's input is the whole response.
        _LOGGER.debug(
            "Registration response was only partially valid: %s",
            _validation_error_summary(err),
        )
    return RegisteredClient(client_id, client_secret, method)


def _client_secret_from_response(value: Any, method: TokenEndpointAuthMethod) -> str:
    """Return the issued client secret.

    Confidential methods need a non-empty string secret. A missing secret,
    or a falsey non-string, is not turned into an empty string. Public
    clients may omit the secret.
    """
    if method == TOKEN_ENDPOINT_AUTH_NONE:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        raise ClientRegistrationError("Registration response client_secret was invalid")
    if not isinstance(value, str) or not value:
        raise ClientRegistrationError(
            "Registration response did not include client_secret"
        )
    return value


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


def _validation_error_summary(err: ValidationError) -> str:
    """Return field locations and error types, without input values."""
    details = err.errors(
        include_input=False,
        include_url=False,
        include_context=False,
    )
    return "; ".join(
        f"{'.'.join(str(part) for part in detail['loc'])}: {detail['type']}"
        for detail in details
    )


def _field_or_omitted(payload: Mapping[str, Any], key: str) -> Any:
    """Return a response field, or a sentinel when the key is absent.

    ``Mapping.get`` cannot tell an omitted field from an explicit null.
    """
    if key not in payload:
        return _OMITTED
    return payload[key]


def _require_registered_redirect_uri(value: Any, redirect_uri: str) -> None:
    """Reject a response that does not register the callback we will use.

    An omitted list is accepted: some servers return only the client id. An
    explicit null or list must include the callback from this request.
    """
    if value is _OMITTED:
        return
    if not isinstance(value, list) or any(not isinstance(uri, str) for uri in value):
        raise ClientRegistrationError("Registration response redirect_uris was invalid")
    if redirect_uri not in value:
        raise ClientRegistrationError(
            "Registration response did not include the redirect URI"
        )


def _require_authorization_code_grants(payload: Mapping[str, Any]) -> None:
    """Reject a response that drops the grants this client will use.

    Omitted grant_types and response_types stay compatible with servers that
    return only a client id. An explicit list must include authorization_code,
    refresh_token, and the code response type.
    """
    grant_types = _field_or_omitted(payload, "grant_types")
    if grant_types is not _OMITTED and (
        not isinstance(grant_types, list)
        or any(not isinstance(grant, str) for grant in grant_types)
        or "authorization_code" not in grant_types
        or "refresh_token" not in grant_types
    ):
        raise ClientRegistrationError(
            "Registration response did not include the required grant types"
        )
    response_types = _field_or_omitted(payload, "response_types")
    if response_types is not _OMITTED and (
        not isinstance(response_types, list)
        or any(not isinstance(response_type, str) for response_type in response_types)
        or "code" not in response_types
    ):
        raise ClientRegistrationError(
            "Registration response did not include the code response type"
        )


def _require_granted_scopes(value: Any, requested_scopes: tuple[str, ...]) -> None:
    """Reject a response whose scope does not cover the request.

    An omitted scope is accepted. An explicit null or other non-string is
    not. A string must include every scope this registration asked for.
    """
    if value is _OMITTED:
        return
    if not isinstance(value, str):
        raise ClientRegistrationError("Registration response scope was invalid")
    granted = set(value.split())
    if not set(requested_scopes).issubset(granted):
        raise ClientRegistrationError(
            "Registration response did not grant the requested scopes"
        )


def _reject_expiring_client_secret(value: Any, method: TokenEndpointAuthMethod) -> None:
    """Reject a confidential client secret that will expire.

    RFC 7591 uses 0 when the secret does not expire. Any other timestamp is a
    finite lifetime, which is refused until credential rotation exists. Public
    clients authenticate with PKCE and do not send a client secret, so an
    expiry echoed for that unused secret is ignored.
    """
    if method == TOKEN_ENDPOINT_AUTH_NONE or value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ClientRegistrationError("client_secret_expires_at was invalid")
    if value == 0:
        return
    raise ClientSecretExpiresError(
        "Authorization server issued a client secret that expires"
    )
