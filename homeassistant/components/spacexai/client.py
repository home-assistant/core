"""Async client boundary for SpaceXAI."""

import asyncio
from asyncio import Lock
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from aiohttp import ClientError, ClientTimeout, ContentTypeError
import openai
from openai import AsyncStream
from openai.types import Model as OpenAIModel
from openai.types.responses import ResponseInputParam, ResponseStreamEvent
from pydantic import ValidationError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    API_BASE_URL,
    CREATE_TIMEOUT,
    HTTP_TIMEOUT_SECONDS,
    REVOCATION_URL,
    USERINFO_URL,
)
from .errors import (
    AccountMismatchError,
    AuthenticationRejectedError,
    ConnectionFailureError,
    ErrorContext,
    MalformedProviderResponseError,
    ModelNotEntitledError,
    NoConversationModelsError,
    Operation,
    PermanentProviderError,
    QuotaLimitedError,
    RateLimitedError,
    ReauthenticationRequiredError,
    RefreshRejectedError,
    RequestTimeoutError,
    SpaceXAIError,
    SubscriptionNotEntitledError,
    TransientProviderError,
)

HTTP_TIMEOUT = ClientTimeout(total=HTTP_TIMEOUT_SECONDS)


class AccessTokenProvider(Protocol):
    """Provide a valid OAuth access token."""

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""


@dataclass(frozen=True, slots=True)
class StaticAccessTokenProvider:
    """Access token provider used while configuring the integration."""

    access_token: str

    async def async_get_access_token(self) -> str:
        """Return the configuration-flow access token."""
        return self.access_token


@dataclass(slots=True)
class OAuthAccessTokenProvider:
    """Access token provider backed by Home Assistant OAuth."""

    session: OAuth2Session

    async def async_get_access_token(self) -> str:
        """Refresh if needed and return the current access token."""
        try:
            await self.session.async_ensure_token_valid()
        except OAuth2TokenRequestReauthError as err:
            raise RefreshRejectedError(
                "OAuth refresh was rejected",
                context=ErrorContext(operation=Operation.REFRESH),
            ) from err
        except OAuth2TokenRequestTransientError as err:
            raise TransientProviderError(
                "OAuth refresh failed transiently",
                context=ErrorContext(
                    operation=Operation.REFRESH,
                    status=err.status,
                ),
            ) from err
        except TimeoutError as err:
            raise RequestTimeoutError(
                "OAuth refresh timed out",
                context=ErrorContext(operation=Operation.REFRESH),
            ) from err
        except (ClientError, OAuth2TokenRequestError) as err:
            raise ConnectionFailureError(
                "OAuth refresh could not be completed",
                context=ErrorContext(operation=Operation.REFRESH),
            ) from err

        access_token = self.session.token.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise MalformedProviderResponseError(
                "OAuth token response omitted access_token",
                context=ErrorContext(operation=Operation.REFRESH),
            )
        return access_token


@dataclass(frozen=True, slots=True)
class AccountInfo:
    """Parsed account identity."""

    subject: str
    name: str | None
    email: str | None

    @property
    def display_name(self) -> str:
        """Return a safe display name for the config entry."""
        return self.name or self.email or "SpaceXAI"


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Model available to the authenticated account."""

    id: str
    owner: str
    aliases: tuple[str, ...] = ()

    @property
    def selectable_ids(self) -> tuple[str, ...]:
        """Return requestable model identifiers for this catalog entry."""
        return (self.id, *self.aliases)


@dataclass(frozen=True, slots=True)
class ProviderSnapshot:
    """Validated provider state cached in runtime data."""

    account: AccountInfo
    models: tuple[ModelInfo, ...]

    def has_model(self, model: str) -> bool:
        """Return whether the account is entitled to a model."""
        return any(model in item.selectable_ids for item in self.models)


class SpaceXAIClient:
    """Narrow async wrapper around the OAuth and Responses APIs."""

    def __init__(
        self,
        hass: HomeAssistant,
        token_provider: AccessTokenProvider,
        *,
        runtime_session: bool,
    ) -> None:
        """Initialize the client."""
        self._hass = hass
        self._token_provider = token_provider
        self._runtime_session = runtime_session
        self._sdk_client: openai.AsyncOpenAI | None = None
        self._sdk_lock = Lock()

    async def async_get_account(self) -> AccountInfo:
        """Fetch and parse the current account identity."""
        token = await self._token_provider.async_get_access_token()
        session = async_get_clientsession(self._hass)
        context = ErrorContext(operation=Operation.ACCOUNT)
        try:
            async with session.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {token}"},
                timeout=HTTP_TIMEOUT,
            ) as response:
                if response.status >= 400:
                    body = await _safe_json(response)
                    raise self._error_for_status(
                        response.status,
                        ErrorContext(
                            operation=Operation.ACCOUNT,
                            status=response.status,
                            provider_code=_provider_error_code(body),
                        ),
                        body=body,
                    )
                payload = await response.json()
        except SpaceXAIError:
            raise
        except (ContentTypeError, TypeError, ValueError) as err:
            raise MalformedProviderResponseError(
                "Account endpoint returned invalid JSON", context=context
            ) from err
        except TimeoutError as err:
            raise RequestTimeoutError(
                "Account endpoint request timed out", context=context
            ) from err
        except ClientError as err:
            raise ConnectionFailureError(
                "Could not connect to the account endpoint", context=context
            ) from err

        if not isinstance(payload, Mapping):
            raise MalformedProviderResponseError(
                "Account endpoint returned a non-object response", context=context
            )
        subject = payload.get("sub")
        name = payload.get("name")
        email = payload.get("email")
        if (
            not isinstance(subject, str)
            or not subject
            or (name is not None and not isinstance(name, str))
            or (email is not None and not isinstance(email, str))
        ):
            raise MalformedProviderResponseError(
                "Account endpoint returned invalid identity fields", context=context
            )
        return AccountInfo(subject=subject, name=name, email=email)

    async def async_get_models(self) -> tuple[ModelInfo, ...]:
        """Return the OAuth-entitled Grok language models."""
        token = await self._token_provider.async_get_access_token()
        context = ErrorContext(operation=Operation.MODELS)
        try:
            async with self._sdk_lock:
                client = await self._async_sdk_client(token)
                page = await client.models.list(timeout=float(HTTP_TIMEOUT_SECONDS))
                models = [
                    ModelInfo(
                        id=model.id,
                        owner=model.owned_by,
                        aliases=_model_aliases(model),
                    )
                    async for model in page
                    if _is_conversation_model(model)
                ]
        except (openai.OpenAIError, ValidationError) as err:
            raise self.translate_sdk_error(err, context) from err

        models.sort(key=lambda model: model.id)
        if not models:
            raise NoConversationModelsError(
                "The account has no available conversation models",
                context=ErrorContext(operation=Operation.MODELS),
            )
        return tuple(models)

    async def async_validate(
        self, *, expected_subject: str | None = None
    ) -> ProviderSnapshot:
        """Validate identity and discover entitled language models."""
        account = await self.async_get_account()
        if expected_subject is not None and account.subject != expected_subject:
            raise AccountMismatchError(
                "OAuth account does not match the config entry",
                context=ErrorContext(operation=Operation.ACCOUNT),
            )
        models = await self.async_get_models()
        return ProviderSnapshot(account=account, models=models)

    async def async_stream_response(
        self,
        *,
        model: str,
        input: ResponseInputParam,
        tools: Sequence[Mapping[str, Any]],
        max_output_tokens: int,
        prompt_cache_key: str,
    ) -> AsyncStream[ResponseStreamEvent]:
        """Start a streaming Responses API request."""
        token = await self._token_provider.async_get_access_token()
        context = ErrorContext(operation=Operation.RESPONSE, model=model)
        try:
            async with self._sdk_lock:
                client = await self._async_sdk_client(token)
                create_args: dict[str, Any] = {
                    "model": model,
                    "input": input,
                    "tools": list(tools),
                    "max_output_tokens": max_output_tokens,
                    "parallel_tool_calls": False,
                    "prompt_cache_key": prompt_cache_key,
                    "store": False,
                    "include": ["reasoning.encrypted_content"],
                    "stream": True,
                }
                try:
                    async with asyncio.timeout(CREATE_TIMEOUT):
                        return cast(
                            AsyncStream[ResponseStreamEvent],
                            await client.responses.create(**create_args),
                        )
                except TimeoutError as err:
                    raise RequestTimeoutError(
                        "Provider response timed out", context=context
                    ) from err
        except SpaceXAIError:
            raise
        except (openai.OpenAIError, ValidationError) as err:
            raise self.translate_sdk_error(err, context) from err

    async def async_revoke(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str = "",
    ) -> None:
        """Revoke a refresh token when the config entry is removed."""
        session = async_get_clientsession(self._hass)
        context = ErrorContext(operation=Operation.REVOCATION)
        data = {
            "token": refresh_token,
            "token_type_hint": "refresh_token",
            "client_id": client_id,
        }
        if client_secret:
            data["client_secret"] = client_secret
        try:
            async with session.post(
                REVOCATION_URL,
                data=data,
                timeout=HTTP_TIMEOUT,
            ) as response:
                if response.status >= 400:
                    raise self._error_for_status(
                        response.status,
                        ErrorContext(
                            operation=Operation.REVOCATION,
                            status=response.status,
                        ),
                    )
        except SpaceXAIError:
            raise
        except TimeoutError as err:
            raise RequestTimeoutError(
                "Revocation endpoint request timed out", context=context
            ) from err
        except ClientError as err:
            raise ConnectionFailureError(
                "Could not connect to the revocation endpoint", context=context
            ) from err

    async def _async_sdk_client(self, access_token: str) -> openai.AsyncOpenAI:
        """Return a reusable SDK client with the current OAuth token."""
        if self._sdk_client is None:
            self._sdk_client = openai.AsyncOpenAI(
                api_key=access_token,
                base_url=API_BASE_URL,
                http_client=get_async_client(self._hass),
            )
            await self._hass.async_add_executor_job(self._sdk_client.platform_headers)
        else:
            self._sdk_client.api_key = access_token
        return self._sdk_client

    def translate_sdk_error(
        self,
        err: openai.OpenAIError | ValidationError,
        context: ErrorContext,
    ) -> SpaceXAIError:
        """Translate SDK failures at the provider boundary."""
        if isinstance(err, ValidationError):
            return MalformedProviderResponseError(
                "Provider response did not match the SDK schema", context=context
            )
        if isinstance(err, openai.APITimeoutError):
            return RequestTimeoutError("Provider request timed out", context=context)
        if isinstance(err, openai.APIConnectionError):
            return ConnectionFailureError(
                "Could not connect to the provider", context=context
            )
        if isinstance(err, openai.APIStatusError):
            provider_code = _provider_error_code(err.body)
            status_context = ErrorContext(
                operation=context.operation,
                model=context.model,
                status=err.status_code,
                provider_code=provider_code,
                request_id=err.request_id,
            )
            return self._error_for_status(
                err.status_code,
                status_context,
                body=err.body,
            )
        return PermanentProviderError(
            "Provider SDK rejected the operation", context=context
        )

    def _error_for_status(
        self,
        status: int,
        context: ErrorContext,
        *,
        body: object | None = None,
    ) -> SpaceXAIError:
        """Classify provider status codes without exposing response content."""
        if status == 401 or _is_credential_rejection(
            status, context.provider_code, body
        ):
            error_type = (
                ReauthenticationRequiredError
                if self._runtime_session
                else AuthenticationRejectedError
            )
            return error_type("Provider rejected authentication", context=context)
        if status == 402:
            return QuotaLimitedError(
                "Provider reported a quota or billing limitation", context=context
            )
        if status == 403:
            if _is_subscription_denial(status, context.provider_code, body) or (
                context.operation
                in (Operation.ACCOUNT, Operation.MODELS, Operation.RESPONSE)
                and not _is_permission_denial(context.provider_code, body)
            ):
                return SubscriptionNotEntitledError(
                    "Account is not entitled for subscription-backed Grok access",
                    context=context,
                )
            return PermanentProviderError(
                "Provider denied permission for the operation", context=context
            )
        if status == 404 and context.model is not None:
            return ModelNotEntitledError(
                "Configured model is not available to this account", context=context
            )
        if status == 408:
            return RequestTimeoutError("Provider request timed out", context=context)
        if status == 429:
            return RateLimitedError("Provider rate limit reached", context=context)
        if 500 <= status <= 599:
            return TransientProviderError(
                "Provider reported a transient failure", context=context
            )
        return PermanentProviderError(
            "Provider rejected the operation", context=context
        )


def _provider_error_code(body: object) -> str | None:
    """Extract a provider error code from an SDK response body."""
    if not isinstance(body, Mapping):
        return None
    error = body.get("error")
    if isinstance(error, Mapping):
        code = error.get("code") or error.get("type")
    else:
        code = body.get("code")
    return code if isinstance(code, str) else None


def _provider_error_message(body: object) -> str | None:
    """Extract a provider error message used only for classification."""
    if not isinstance(body, Mapping):
        return None
    error = body.get("error")
    if isinstance(error, Mapping):
        message = error.get("message")
    elif isinstance(error, str):
        message = error
    else:
        message = body.get("error")
        if not isinstance(message, str):
            message = body.get("message")
    return message if isinstance(message, str) else None


def _is_credential_rejection(
    status: int,
    provider_code: str | None,
    body: object | None,
) -> bool:
    """Return whether the provider rejected credentials with a non-401 status."""
    if status != 400:
        return False
    code = (provider_code or "").lower()
    if code.startswith("unauthenticated") or code == "invalid_token":
        return True
    message = (_provider_error_message(body) or "").lower()
    return "incorrect api key" in message or "no credentials" in message


def _is_subscription_denial(
    status: int,
    provider_code: str | None,
    body: object | None,
) -> bool:
    """Return whether a response explicitly signals subscription ineligibility."""
    if status != 403:
        return False
    code = (provider_code or "").lower()
    if code in {
        "subscription_required",
        "subscription_not_entitled",
        "not_entitled",
        "insufficient_permissions",
    }:
        return True
    message = (_provider_error_message(body) or "").lower()
    return "subscription" in message and (
        "entitled" in message or "required" in message or "inactive" in message
    )


def _is_permission_denial(
    provider_code: str | None,
    body: object | None,
) -> bool:
    """Return whether a 403 is an explicit non-subscription permission denial."""
    code = (provider_code or "").lower()
    if code in {"permission_denied", "access_denied", "forbidden"}:
        return True
    message = (_provider_error_message(body) or "").lower()
    return "permission denied" in message or "access denied" in message


def _model_aliases(model: OpenAIModel) -> tuple[str, ...]:
    """Extract provider aliases that can be used as request model IDs."""
    extra = model.model_extra or {}
    aliases = extra.get("aliases")
    if not isinstance(aliases, list):
        return ()
    return tuple(
        alias
        for alias in aliases
        if isinstance(alias, str) and alias and alias != model.id
    )


def _is_conversation_model(model: OpenAIModel) -> bool:
    """Return whether xAI model metadata identifies text output."""
    extra = model.model_extra or {}
    output_modalities = extra.get("output_modalities")
    if isinstance(output_modalities, list):
        return "text" in output_modalities
    return isinstance(extra.get("completion_text_token_price"), int)


async def _safe_json(response: Any) -> object | None:
    """Best-effort JSON body used only for error classification."""
    try:
        payload: object = await response.json(content_type=None)
    except ContentTypeError, TypeError, ValueError:
        return None
    return payload
