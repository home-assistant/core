"""Sign in with ChatGPT (ChatGPT plan usage) authentication.

This implements the OAuth flow documented at
https://developers.openai.com/siwc/token-sharing-open-source/ which lets an
open-source, locally hosted app use an eligible ChatGPT plan for eligible
Responses API requests. The access token obtained here is used as the bearer
token against ``https://api.openai.com/v1`` instead of an API key.
"""

import asyncio
import base64
from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import logging
import secrets
from typing import Any, cast, override
from urllib.parse import parse_qsl, urlencode, urlparse
import uuid

import httpx2
import jwt
import openai

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_EMAIL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    AUTH_METHOD_CHATGPT,
    CONF_AUTH_METHOD,
    CONF_EARLIEST_REFRESH_AT,
    CONF_EXPIRES_AT,
    CONF_EXT_AGENT_HOST_ID,
    CONF_ID_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_SCOPES,
    CONF_SUB,
)

_LOGGER = logging.getLogger(__name__)

AUTHORIZE_URL = "https://auth.openai.com/api/accounts/authorize"
TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
JWKS_URL = "https://auth.openai.com/.well-known/jwks.json"
ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
MODELS_URL = "https://api.openai.com/v1/models"

# The callback URI must be an HTTP loopback address on 127.0.0.1; only the port
# may vary. A fixed port keeps the URI stable between authorization attempts.
REDIRECT_URI = "http://127.0.0.1:1455/auth/callback"

# `dynamic_agent_client` is the first-time registration entrypoint only. It must
# never be stored: the callback returns the issued client id (oaiapp_...) which
# is used for the code exchange and all later authorizations.
DYNAMIC_AGENT_CLIENT = "dynamic_agent_client"
CLIENT_ID_PREFIX = "oaiapp_"
AGENT_NAME_HINT = "Home Assistant"
SCOPE = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
# Granted scope required before the ChatGPT plan may be used.
PLAN_SCOPE = "chatgpt.tokens.use.direct"

# Refresh the access token this long before it expires. Access tokens live one
# hour and refresh tokens 30 days.
TOKEN_EXPIRY_MARGIN = timedelta(minutes=5)
HTTP_TIMEOUT = 30
JWKS_CACHE_TTL = timedelta(hours=1)
JWKS_CACHE_DATA_KEY = "openai_conversation.chatgpt.jwks"

STORAGE_KEY = "openai_conversation.chatgpt"
STORAGE_VERSION = 1

# Token endpoint errors which mean the refresh token can never be used again.
FATAL_REFRESH_ERRORS = frozenset(
    {
        "invalid_grant",
        "invalid_client",
        "invalid_refresh_token",
        "refresh_token_expired",
        "refresh_token_invalidated",
        "refresh_token_reused",
        "token_expired",
    }
)

# Errors returned by the subscription route itself (inference requests).
SUBSCRIPTION_INFERENCE_ERROR_HINTS = {
    "subscription_sharing_user_not_eligible": (
        "This ChatGPT account is not eligible to use the ChatGPT plan with "
        "Home Assistant. Check your plan in ChatGPT settings."
    ),
    "subscription_sharing_usage_limit_exceeded": (
        "The ChatGPT plan usage limit was reached. Check ChatGPT settings -> "
        "Usage to see the remaining plan usage."
    ),
    "subscription_sharing_usage_unavailable": (
        "ChatGPT plan usage is currently unavailable, please retry later."
    ),
    "subscription_sharing_route_not_supported": (
        "This request is not supported by ChatGPT plan usage."
    ),
    "subscription_sharing_unsupported_capability": (
        "This request uses a capability which ChatGPT plan usage does not support."
    ),
    "subscription_sharing_invalid_user": (
        "The ChatGPT sign-in is no longer valid. Please sign in with ChatGPT again."
    ),
}

# Parameters the ChatGPT plan usage route rejects. Everything else in the
# request builder is either required (model/input) or accepted.
SUBSCRIPTION_UNSUPPORTED_PARAMS = (
    "background",
    "conversation",
    "max_output_tokens",
    "max_tool_calls",
    "metadata",
    "moderation",
    "multi_agent",
    "prompt",
    "prompt_cache_key",
    "prompt_cache_options",
    "prompt_cache_retention",
    "safety_identifier",
    "service_tier",
    "temperature",
    "top_logprobs",
    "top_p",
    "truncation",
    "user",
)

# Hosted tools which the subscription route does not provide. Web search is
# still offered by the route, subject to the account's plan and policy.
SUBSCRIPTION_UNSUPPORTED_TOOL_TYPES = (
    "code_interpreter",
    "file_search",
    "image_generation",
    "mcp",
    "tool_search",
)

# The subscription route requires unsaved, streamed responses.
SUBSCRIPTION_STORE = False
SUBSCRIPTION_STREAM = True

# Placeholder value the OpenAI SDK insists on; the real credential is the OAuth
# access token attached by `ChatGPTSubscriptionClient.custom_auth`.
PLACEHOLDER_API_KEY = "chatgpt-plan"

# Models which were observed in the catalog of a ChatGPT plan account. The
# catalog is authoritative and is used whenever it can be read, but it can be
# unavailable (OpenAI answered a transient HTTP 520 while this was written) and
# the plan usage route rejects the regular API default model, so these are
# offered as suggestions in that case. The model field stays editable, so a
# model outside this list can still be used.
SUBSCRIPTION_MODEL_SUGGESTIONS: list[str] = [
    "gpt-6.1-sol",
    "gpt-6-astra",
    "gpt-6-sol",
    "gpt-6-luna",
    "gpt-reserve",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-daybreak-blue-latest",
    "gpt-5.5",
    "codex-auto-review",
]


def subscription_model_options(models: list[str]) -> list[str]:
    """Return the models to offer, falling back to the known suggestions."""
    return models or SUBSCRIPTION_MODEL_SUGGESTIONS


def is_chatgpt_entry(entry: ConfigEntry) -> bool:
    """Return if a config entry authenticates with a ChatGPT plan.

    API key entries keep the historical layout and have no auth method key.
    """
    return entry.data.get(CONF_AUTH_METHOD) == AUTH_METHOD_CHATGPT


@dataclass
class ChatGPTCredentials:
    """Credentials of one Sign in with ChatGPT registration."""

    client_id: str
    ext_agent_host_id: str
    sub: str
    email: str | None
    access_token: str
    refresh_token: str
    id_token: str
    expires_at: datetime
    scopes: list[str]
    earliest_refresh_at: datetime | None = None

    @property
    def unique_id(self) -> str:
        """Return the account identity scoped to this registration.

        The subject identifies the ChatGPT account, the issued client id the
        registration (one account can have several workspaces registered).
        """
        return f"{self.sub}:{self.client_id}"

    def as_entry_data(self) -> dict[str, Any]:
        """Return the credentials as config entry data."""
        data: dict[str, Any] = {
            CONF_AUTH_METHOD: AUTH_METHOD_CHATGPT,
            CONF_CLIENT_ID: self.client_id,
            CONF_EXT_AGENT_HOST_ID: self.ext_agent_host_id,
            CONF_SUB: self.sub,
            CONF_ACCESS_TOKEN: self.access_token,
            CONF_REFRESH_TOKEN: self.refresh_token,
            CONF_ID_TOKEN: self.id_token,
            CONF_EXPIRES_AT: self.expires_at.isoformat(),
            CONF_SCOPES: self.scopes,
        }
        if self.email is not None:
            data[CONF_EMAIL] = self.email
        if self.earliest_refresh_at is not None:
            data[CONF_EARLIEST_REFRESH_AT] = self.earliest_refresh_at.isoformat()
        return data

    @classmethod
    def from_entry_data(cls, data: Mapping[str, Any]) -> ChatGPTCredentials:
        """Build credentials from config entry data."""
        return cls(
            client_id=data[CONF_CLIENT_ID],
            ext_agent_host_id=data.get(CONF_EXT_AGENT_HOST_ID, ""),
            sub=data.get(CONF_SUB, ""),
            email=data.get(CONF_EMAIL),
            access_token=data[CONF_ACCESS_TOKEN],
            refresh_token=data[CONF_REFRESH_TOKEN],
            id_token=data.get(CONF_ID_TOKEN, ""),
            expires_at=dt_util.parse_datetime(data[CONF_EXPIRES_AT])
            or dt_util.utcnow(),
            scopes=list(data.get(CONF_SCOPES, [])),
            earliest_refresh_at=dt_util.parse_datetime(
                data.get(CONF_EARLIEST_REFRESH_AT, "")
            ),
        )


async def async_get_agent_host_id(hass: HomeAssistant) -> str:
    """Return the stable ``ext_agent_host_id`` of this installation.

    The host id identifies the host the app runs on, not the signed in account,
    and every registration of this instance shares it. It is kept in Home
    Assistant storage instead of the config entry so that it survives entry
    deletion and re-registration.

    A UUID based host id is documented as a supported alternative to a JWK
    thumbprint URI and needs no key management.
    """
    store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    if (stored := await store.async_load()) and (
        host_id := stored.get(CONF_EXT_AGENT_HOST_ID)
    ):
        if isinstance(host_id, str):
            return host_id
    host_id = f"urn:uuid:{uuid.uuid4()}"
    await store.async_save({CONF_EXT_AGENT_HOST_ID: host_id})
    return host_id


@dataclass
class AuthorizationRequest:
    """A pending SIWC authorization attempt."""

    url: str
    state: str
    nonce: str
    code_verifier: str
    redirect_uri: str
    ext_agent_host_id: str
    # The client id to exchange the code with: `dynamic_agent_client` until the
    # callback returns the issued client id.
    client_id: str
    registration: bool


def _create_pkce_pair() -> tuple[str, str]:
    """Create a PKCE verifier and its S256 challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def create_authorization_request(
    *,
    client_id: str | None,
    ext_agent_host_id: str,
    id_token_hint: str | None = None,
) -> AuthorizationRequest:
    """Build the authorization URL for a new or a returning ChatGPT account.

    A fresh state, nonce and PKCE verifier are generated for every attempt.
    """
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = _create_pkce_pair()

    registration = client_id is None
    params = {
        "response_type": "code",
        "client_id": DYNAMIC_AGENT_CLIENT if registration else client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "resource": RESOURCE,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "ext_agent_host_id": ext_agent_host_id,
    }
    if registration:
        # agent_name_hint is display metadata and is only sent for the first
        # (dynamic client registration) authorization request.
        params["agent_name_hint"] = AGENT_NAME_HINT
    if id_token_hint:
        params["id_token_hint"] = id_token_hint

    return AuthorizationRequest(
        url=f"{AUTHORIZE_URL}?{urlencode(params)}",
        state=state,
        nonce=nonce,
        code_verifier=verifier,
        redirect_uri=REDIRECT_URI,
        ext_agent_host_id=ext_agent_host_id,
        client_id=client_id or DYNAMIC_AGENT_CLIENT,
        registration=registration,
    )


def parse_callback_url(url: str) -> dict[str, str]:
    """Parse the query of the URL the user's browser ended up on.

    The loopback callback is normally on a different machine than Home
    Assistant, so the page itself cannot be loaded. The address bar still holds
    the OAuth parameters, which is all that is needed.
    """
    return dict(parse_qsl(urlparse(url.strip()).query))


def _error_code(body: Any) -> str | None:
    """Return the OAuth error code of a token endpoint response body."""
    match body:
        case {"error": {"code": str(code)}}:
            return code
        case {"error": str(code)}:
            return code
        case {"code": str(code)}:
            return code
    return None


def _error_message(body: Any) -> str:
    """Return the message of a token endpoint error response body."""
    match body:
        case {"error": {"message": str(message)}}:
            return message
        case {"error_description": str(description)}:
            return description
        case {"error": {"error_description": str(description)}}:
            return description
    return "unknown error"


async def async_token_request(
    hass: HomeAssistant,
    data: dict[str, str],
    *,
    fatal_errors: bool = False,
) -> dict[str, Any]:
    """POST a form encoded grant to the SIWC token endpoint.

    ``fatal_errors`` maps the errors which invalidate the stored refresh token
    to `ConfigEntryAuthFailed` so Home Assistant starts the reauth flow.
    """
    client = get_async_client(hass)
    try:
        response = await client.post(TOKEN_URL, data=data, timeout=HTTP_TIMEOUT)
    except httpx2.HTTPError as err:
        raise HomeAssistantError(f"Error talking to OpenAI: {err}") from err

    if response.status_code == 200:
        try:
            return cast("dict[str, Any]", response.json())
        except ValueError as err:
            raise HomeAssistantError("Invalid token response from OpenAI") from err

    try:
        body = response.json()
    except ValueError:
        body = None
    code = _error_code(body)
    message = _error_message(body)

    if fatal_errors and code in FATAL_REFRESH_ERRORS:
        raise ConfigEntryAuthFailed(
            f"Sign in with ChatGPT authentication failed ({code}): {message}"
        )

    raise HomeAssistantError(f"Sign in with ChatGPT failed ({code}): {message}")


async def async_get_jwks(hass: HomeAssistant, *, force: bool = False) -> dict[str, Any]:
    """Return the OpenAI JWKS, cached for a while."""
    cache: dict[str, Any] = hass.data.setdefault(JWKS_CACHE_DATA_KEY, {})
    if not force and (cached := cache.get("jwks")) and cached[0] > dt_util.utcnow():
        return cast("dict[str, Any]", cached[1])

    client = get_async_client(hass)
    try:
        response = await client.get(JWKS_URL, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        jwks: dict[str, Any] = response.json()
    except httpx2.HTTPError as err:
        raise HomeAssistantError(
            f"Could not fetch the OpenAI signing keys: {err}"
        ) from err
    except ValueError as err:
        raise HomeAssistantError("Could not parse the OpenAI signing keys") from err

    cache["jwks"] = (dt_util.utcnow() + JWKS_CACHE_TTL, jwks)
    return jwks


async def _async_get_jwk_set(
    hass: HomeAssistant, *, force: bool = False
) -> jwt.PyJWKSet:
    """Return the OpenAI signing keys as a JWK set."""
    try:
        return jwt.PyJWKSet.from_dict(await async_get_jwks(hass, force=force))
    except jwt.PyJWTError as err:
        raise HomeAssistantError(f"Invalid signing keys: {err}") from err


async def async_validate_id_token(
    hass: HomeAssistant, id_token: str, *, client_id: str, nonce: str
) -> Mapping[str, Any]:
    """Validate an ID token against the OpenAI JWKS and return its claims.

    The issuer, the audience (the issued client id), the expiry and the nonce
    of this authorization attempt are all verified.
    """
    try:
        key_id = jwt.get_unverified_header(id_token).get("kid")
    except jwt.PyJWTError as err:
        raise HomeAssistantError(f"Invalid ID token: {err}") from err

    jwk_set = await _async_get_jwk_set(hass)

    key = next((key for key in jwk_set.keys if key.key_id == key_id), None)
    if key is None:
        # The signing keys rotate, so a key this cache does not know yet may
        # simply be newer than our copy.
        jwk_set = await _async_get_jwk_set(hass, force=True)
        key = next((key for key in jwk_set.keys if key.key_id == key_id), None)
    if key is None:
        raise HomeAssistantError(f"Unknown ID token signing key: {key_id}")

    try:
        claims = jwt.decode(
            id_token,
            key.key,
            algorithms=[key.algorithm_name or "RS256"],
            audience=client_id,
            issuer=ISSUER,
        )
    except jwt.PyJWTError as err:
        raise HomeAssistantError(f"Invalid ID token: {err}") from err

    if claims.get("nonce") != nonce:
        raise HomeAssistantError("Invalid ID token: nonce mismatch")

    return claims


def _parse_optional_datetime(value: Any) -> datetime | None:
    """Parse an optional ISO 8601 timestamp."""
    if not value or not isinstance(value, str):
        return None
    return dt_util.parse_datetime(value)


def credentials_from_token(
    token: Mapping[str, Any],
    *,
    client_id: str,
    ext_agent_host_id: str,
    previous: ChatGPTCredentials | None = None,
    sub: str | None = None,
    email: str | None = None,
) -> ChatGPTCredentials:
    """Build credentials from a token endpoint response.

    Refresh tokens rotate on every refresh, so the response always replaces the
    stored credentials. Fields the response does not repeat are kept from
    ``previous``.
    """
    scopes = str(token.get("scope", "")).split()
    expires_in = token.get("expires_in")
    return ChatGPTCredentials(
        client_id=client_id,
        ext_agent_host_id=ext_agent_host_id,
        sub=sub if sub is not None else (previous.sub if previous else ""),
        email=email if email is not None else (previous.email if previous else None),
        access_token=token["access_token"],
        refresh_token=token.get("refresh_token")
        or (previous.refresh_token if previous else ""),
        id_token=token.get("id_token") or (previous.id_token if previous else ""),
        expires_at=dt_util.utcnow()
        + timedelta(seconds=int(expires_in) if expires_in else 3600),
        scopes=scopes or (previous.scopes if previous else []),
        earliest_refresh_at=_parse_optional_datetime(token.get("earliest_refresh_at")),
    )


class ChatGPTAuth:
    """Manage the SIWC token lifecycle of one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        credentials: ChatGPTCredentials,
    ) -> None:
        """Initialize the token manager."""
        self.hass = hass
        self.entry = entry
        self.credentials = credentials
        self._lock = asyncio.Lock()
        self._reauth_started = False

    @classmethod
    def from_entry(cls, hass: HomeAssistant, entry: ConfigEntry) -> ChatGPTAuth:
        """Build the token manager of a config entry."""
        return cls(hass, entry, ChatGPTCredentials.from_entry_data(entry.data))

    async def async_get_access_token(self) -> str:
        """Return a valid access token, refreshing it when it is about to expire.

        This is used as the async `api_key` provider of the OpenAI client, so
        the token is checked (and refreshed) before every request.
        """
        async with self._lock:
            if self._async_needs_refresh():
                await self._async_refresh()
        return self.credentials.access_token

    @callback
    def _async_needs_refresh(self) -> bool:
        """Return if the access token should be refreshed."""
        now = dt_util.utcnow()
        if (
            self.credentials.earliest_refresh_at is not None
            and now < self.credentials.earliest_refresh_at
        ):
            # The token endpoint rejects refresh attempts before this time.
            return False
        return now >= self.credentials.expires_at - TOKEN_EXPIRY_MARGIN

    async def async_handle_authentication_error(self) -> None:
        """Refresh the token after the API rejected the access token."""
        async with self._lock:
            if (
                self.credentials.earliest_refresh_at is not None
                and dt_util.utcnow() < self.credentials.earliest_refresh_at
            ):
                # The token endpoint refuses refreshes before this time, so the
                # rejected request was not a token expiry problem.
                return
            await self._async_refresh()

    async def _async_refresh(self) -> None:
        """Exchange the refresh token for a new set of tokens."""
        try:
            token = await async_token_request(
                self.hass,
                {
                    "grant_type": "refresh_token",
                    "client_id": self.credentials.client_id,
                    "refresh_token": self.credentials.refresh_token,
                    "resource": RESOURCE,
                },
                fatal_errors=True,
            )
        except ConfigEntryAuthFailed:
            self._async_start_reauth()
            raise

        self._async_store(
            credentials_from_token(
                token,
                client_id=self.credentials.client_id,
                ext_agent_host_id=self.credentials.ext_agent_host_id,
                previous=self.credentials,
            )
        )

    @callback
    def _async_store(self, credentials: ChatGPTCredentials) -> None:
        """Persist the (rotated) credentials atomically."""
        self.credentials = credentials
        self.hass.config_entries.async_update_entry(
            self.entry, data=credentials.as_entry_data()
        )

    @callback
    def _async_start_reauth(self) -> None:
        """Start the reauth flow, once."""
        if self._reauth_started:
            return
        self._reauth_started = True
        self.entry.async_start_reauth(self.hass)


class ChatGPTSubscriptionAuth(httpx2.Auth):
    """Attach the SIWC access token and refresh it once on a 401."""

    def __init__(self, auth: ChatGPTAuth) -> None:
        """Initialize the auth flow."""
        self._auth = auth

    @override
    async def async_auth_flow(
        self, request: httpx2.Request
    ) -> AsyncGenerator[httpx2.Request, httpx2.Response]:
        """Attach the access token, refreshing it when it was rejected."""
        request.headers["Authorization"] = (
            f"Bearer {await self._auth.async_get_access_token()}"
        )
        response = yield request
        if response.status_code == 401:
            await self._auth.async_handle_authentication_error()
            request.headers["Authorization"] = (
                f"Bearer {self._auth.credentials.access_token}"
            )
            yield request


class ChatGPTSubscriptionClient(openai.AsyncOpenAI):
    """OpenAI client authenticating with a ChatGPT plan subscription."""

    def __init__(
        self,
        auth: ChatGPTAuth,
        http_client: httpx2.AsyncClient,
        **options: Any,
    ) -> None:
        """Initialize the client."""
        self.auth = auth
        # A ChatGPT plan has no API key: the bearer token is attached per request
        # by `custom_auth`, which also refreshes it. The SDK still requires a
        # non-empty `api_key` to build a client, and it does not support a
        # callable one (that raises inside the request).
        options.pop("api_key", None)
        super().__init__(
            api_key=PLACEHOLDER_API_KEY, http_client=http_client, **options
        )

    @override
    def with_options(self, **options: Any) -> ChatGPTSubscriptionClient:
        """Return a copy of this client which keeps the ChatGPT plan sign in.

        The base implementation copies a client with `type(self)(**options)`,
        which would not carry the sign in of this instance.
        """
        options.setdefault("http_client", self._client)
        return ChatGPTSubscriptionClient(self.auth, **options)

    @property
    @override
    def custom_auth(self) -> httpx2.Auth | None:
        """Return the token refreshing auth flow."""
        return ChatGPTSubscriptionAuth(self.auth)


async def async_get_subscription_models(
    hass: HomeAssistant, auth: ChatGPTAuth
) -> list[str]:
    """Return the model slugs offered to a ChatGPT plan account.

    The plan usage route serves a non-standard catalog body (a `models` list of
    objects carrying a `slug`) which the OpenAI SDK cannot parse, so the request
    is made directly.
    """
    return await _async_fetch_subscription_models(
        hass, await auth.async_get_access_token()
    )


async def async_get_subscription_models_for_credentials(
    hass: HomeAssistant, credentials: ChatGPTCredentials
) -> list[str]:
    """Return the model slugs of an account which is not stored in an entry yet.

    Used while creating or converting a config entry, when there is no
    `ChatGPTAuth` (and therefore no config entry) to supply the access token.
    """
    return await _async_fetch_subscription_models(hass, credentials.access_token)


async def _async_fetch_subscription_models(
    hass: HomeAssistant, access_token: str
) -> list[str]:
    """Return the model slugs offered to a ChatGPT plan account."""
    client = get_async_client(hass)
    try:
        response = await client.get(
            MODELS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=HTTP_TIMEOUT,
        )
    except httpx2.HTTPError as err:
        raise HomeAssistantError(f"Error talking to OpenAI: {err}") from err

    if response.status_code in (401, 403):
        raise ConfigEntryAuthFailed(
            "Sign in with ChatGPT authentication failed while listing models"
        )

    try:
        response.raise_for_status()
    except httpx2.HTTPError as err:
        raise HomeAssistantError(f"Error listing OpenAI models: {err}") from err

    try:
        payload = response.json()
    except ValueError as err:
        raise HomeAssistantError("Invalid model catalog response from OpenAI") from err

    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise HomeAssistantError(
            "The model catalog response from OpenAI did not contain a models list"
        )

    slugs: list[str] = [
        item["slug"]
        for item in models
        if isinstance(item, dict) and isinstance(item.get("slug"), str)
    ]
    return slugs


def subscription_error_message(err: openai.OpenAIError) -> str | None:
    """Return a helpful message for a subscription route error."""
    code: Any = getattr(err, "code", None)
    if isinstance(code, str) and (hint := SUBSCRIPTION_INFERENCE_ERROR_HINTS.get(code)):
        return hint
    if isinstance(err, openai.AuthenticationError):
        return SUBSCRIPTION_INFERENCE_ERROR_HINTS["subscription_sharing_invalid_user"]
    return None


def shape_request_for_subscription(
    model_args: dict[str, Any],
    messages: list[Any],
) -> None:
    """Adapt a Responses API request for the ChatGPT plan usage route.

    The subscription route only accepts `store: false` together with
    `stream: true` and rejects a documented list of parameters. It also does
    not accept system input items: the system prompt is sent as `instructions`
    instead. Function tools are accepted flat.
    """
    for param in SUBSCRIPTION_UNSUPPORTED_PARAMS:
        model_args.pop(param, None)

    model_args["store"] = SUBSCRIPTION_STORE
    model_args["stream"] = SUBSCRIPTION_STREAM

    # System/developer messages are not accepted as input items.
    instructions = model_args.get("instructions")
    while messages and (
        isinstance(messages[0], dict)
        and messages[0].get("type") == "message"
        and messages[0].get("role") in ("system", "developer")
    ):
        content = messages.pop(0).get("content")
        if isinstance(content, str):
            instructions = f"{instructions}\n\n{content}" if instructions else content
    if instructions:
        model_args["instructions"] = instructions

    # The route rejects explicit `system` input items.
    for item in messages:
        if (
            isinstance(item, dict)
            and item.get("type") == "message"
            and item.get("role") == "system"
        ):
            item["role"] = "developer"

    # Hosted tools which the subscription route does not provide are removed;
    # function tools are sent flat and `web_search` is kept.
    if tools := model_args.get("tools"):
        kept = [
            tool
            for tool in tools
            if tool.get("type") == "function"
            or tool.get("type") not in SUBSCRIPTION_UNSUPPORTED_TOOL_TYPES
        ]
        if kept:
            model_args["tools"] = kept
        else:
            model_args.pop("tools")

    # Naming a single function as `tool_choice` is not supported.
    if isinstance(model_args.get("tool_choice"), dict):
        model_args.pop("tool_choice")


__all__ = [
    "AUTHORIZE_URL",
    "DYNAMIC_AGENT_CLIENT",
    "PLAN_SCOPE",
    "REDIRECT_URI",
    "RESOURCE",
    "SCOPE",
    "TOKEN_URL",
    "AuthorizationRequest",
    "ChatGPTAuth",
    "ChatGPTCredentials",
    "ChatGPTSubscriptionClient",
    "async_get_agent_host_id",
    "async_get_subscription_models",
    "async_get_subscription_models_for_credentials",
    "async_validate_id_token",
    "create_authorization_request",
    "credentials_from_token",
    "is_chatgpt_entry",
    "parse_callback_url",
    "shape_request_for_subscription",
    "subscription_error_message",
]
