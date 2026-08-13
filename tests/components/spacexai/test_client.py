"""Tests for the typed SpaceXAI client boundary."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientConnectionError
import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAIError
from openai.types import Model
from openai.types.responses import ResponseErrorEvent
from pydantic import ValidationError
import pytest

from homeassistant.components.spacexai.client import (
    AccountInfo,
    OAuthAccessTokenProvider,
    ProviderSnapshot,
    SpaceXAIClient,
    StaticAccessTokenProvider,
    _is_permission_denial,
    _is_subscription_denial,
    _safe_json,
)
from homeassistant.components.spacexai.const import REVOCATION_URL, USERINFO_URL
from homeassistant.components.spacexai.errors import (
    AccountMismatchError,
    AuthenticationRejectedError,
    ConnectionFailureError,
    ErrorCategory,
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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from . import AsyncModelPage, EventStream

from tests.test_util.aiohttp import AiohttpClientMocker


def _client(hass: HomeAssistant, *, runtime: bool = False) -> SpaceXAIClient:
    """Create a test client."""
    return SpaceXAIClient(
        hass,
        StaticAccessTokenProvider("access-token"),
        runtime_session=runtime,
    )


def _status_error(status: int, body: object | None = None) -> APIStatusError:
    """Build an SDK status error for classification tests."""
    return APIStatusError(
        message="failure",
        response=httpx.Response(
            status,
            request=httpx.Request("POST", "https://api.x.ai/v1/responses"),
        ),
        body=body,
    )


async def test_account_identity(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Parse account identity and send a Bearer authorization header."""
    aioclient_mock.get(
        USERINFO_URL,
        json={
            "sub": "account-123",
            "name": "Home User",
            "email": "home@example.com",
        },
    )
    account = await _client(hass).async_get_account()
    assert account.subject == "account-123"
    assert account.display_name == "Home User"
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer access-token"


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param([], id="not-an-object"),
        pytest.param({"name": "Missing subject"}, id="missing-subject"),
        pytest.param({"sub": "id", "email": 42}, id="invalid-email"),
    ],
)
async def test_malformed_account(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    payload: object,
) -> None:
    """Reject malformed provider identity data."""
    aioclient_mock.get(USERINFO_URL, json=payload)
    with pytest.raises(MalformedProviderResponseError):
        await _client(hass).async_get_account()


@pytest.mark.parametrize(
    ("side_effect", "error_type"),
    [
        pytest.param(ClientConnectionError(), ConnectionFailureError, id="connection"),
        pytest.param(TimeoutError(), RequestTimeoutError, id="timeout"),
    ],
)
async def test_account_transport_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    side_effect: Exception,
    error_type: type[Exception],
) -> None:
    """Map account endpoint transport failures to typed errors."""
    aioclient_mock.get(USERINFO_URL, exc=side_effect)
    with pytest.raises(error_type):
        await _client(hass).async_get_account()


async def test_model_discovery_and_filtering(hass: HomeAssistant) -> None:
    """Return only entitled Grok language models, including request aliases."""
    page = AsyncModelPage(
        [
            Model(
                id="grok-4.5",
                created=1,
                object="model",
                owned_by="xai",
                completion_text_token_price=25000,
            ),
            Model(
                id="latest",
                created=1,
                object="model",
                owned_by="xai",
                output_modalities=["text"],
                aliases=["grok-4.3-latest", "grok-latest"],
            ),
            Model(
                id="grok-imagine-1",
                created=1,
                object="model",
                owned_by="xai",
                image_price=1,
            ),
            Model(id="unrelated", created=1, object="model", owned_by="other"),
        ]
    )
    with patch(
        "openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
        return_value=page,
    ):
        models = await _client(hass).async_get_models()
    assert [model.id for model in models] == ["grok-4.5", "latest"]
    assert models[1].aliases == ("grok-4.3-latest", "grok-latest")
    snapshot = ProviderSnapshot(
        account=AccountInfo("sub", "Name", None),
        models=models,
    )
    assert snapshot.has_model("grok-4.3-latest")
    assert not snapshot.has_model("grok-imagine-1")


async def test_model_discovery_iterates_every_page(hass: HomeAssistant) -> None:
    """Discover conversation models beyond the first SDK page."""
    page = AsyncModelPage(
        [
            Model(
                id="grok-page-1",
                created=1,
                object="model",
                owned_by="xai",
                completion_text_token_price=1,
            )
        ],
        [
            Model(
                id="grok-page-2",
                created=1,
                object="model",
                owned_by="xai",
                completion_text_token_price=1,
            )
        ],
    )
    with patch(
        "openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
        return_value=page,
    ):
        models = await _client(hass).async_get_models()
    assert [model.id for model in models] == ["grok-page-1", "grok-page-2"]


async def test_model_discovery_translates_pagination_errors(
    hass: HomeAssistant,
) -> None:
    """Keep later-page SDK failures inside the typed client boundary."""

    class _FailingPage:
        data: list[Model] = []

        def __aiter__(self) -> object:
            return self

        async def __anext__(self) -> Model:
            raise _status_error(503)

    with (
        patch(
            "openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
            return_value=_FailingPage(),
        ),
        pytest.raises(TransientProviderError),
    ):
        await _client(hass).async_get_models()


async def test_no_entitled_models(hass: HomeAssistant) -> None:
    """Treat an empty conversation-model catalog as a distinct entitlement gap."""
    with (
        patch(
            "openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
            return_value=AsyncModelPage(),
        ),
        pytest.raises(NoConversationModelsError),
    ):
        await _client(hass).async_get_models()


async def test_refresh_rejected() -> None:
    """Map a rejected refresh grant separately from inference authentication."""
    session = MagicMock(spec=OAuth2Session)
    session.async_ensure_token_valid = AsyncMock(
        side_effect=OAuth2TokenRequestReauthError(
            request_info=MagicMock(),
            history=(),
            status=400,
            message="invalid_grant",
            headers=None,
            domain="spacexai",
        )
    )
    with pytest.raises(RefreshRejectedError) as raised:
        await OAuthAccessTokenProvider(session).async_get_access_token()
    assert raised.value.category is ErrorCategory.REFRESH_REJECTED


@pytest.mark.parametrize(
    ("side_effect", "error_type"),
    [
        pytest.param(TimeoutError(), RequestTimeoutError, id="timeout"),
        pytest.param(
            OAuth2TokenRequestTransientError(
                request_info=MagicMock(),
                history=(),
                status=503,
                message="unavailable",
                headers=None,
                domain="spacexai",
            ),
            TransientProviderError,
            id="transient",
        ),
        pytest.param(
            ClientConnectionError(),
            ConnectionFailureError,
            id="client-error",
        ),
        pytest.param(
            OAuth2TokenRequestError(
                request_info=MagicMock(),
                history=(),
                status=500,
                message="failed",
                headers=None,
                domain="spacexai",
            ),
            ConnectionFailureError,
            id="token-request-error",
        ),
    ],
)
async def test_refresh_transport_errors(
    side_effect: Exception,
    error_type: type[SpaceXAIError],
) -> None:
    """Map refresh transport failures to typed connection/transient errors."""
    session = MagicMock(spec=OAuth2Session)
    session.async_ensure_token_valid = AsyncMock(side_effect=side_effect)
    with pytest.raises(error_type):
        await OAuthAccessTokenProvider(session).async_get_access_token()


async def test_refresh_missing_access_token() -> None:
    """Reject a refreshed token payload that omits access_token."""
    session = MagicMock(spec=OAuth2Session)
    session.async_ensure_token_valid = AsyncMock()
    session.token = {"token_type": "Bearer"}
    with pytest.raises(MalformedProviderResponseError):
        await OAuthAccessTokenProvider(session).async_get_access_token()


async def test_refresh_returns_access_token() -> None:
    """Return the access token after a successful OAuth refresh."""
    session = MagicMock(spec=OAuth2Session)
    session.async_ensure_token_valid = AsyncMock()
    session.token = {"access_token": "rotated-token", "token_type": "Bearer"}
    assert (
        await OAuthAccessTokenProvider(session).async_get_access_token()
        == "rotated-token"
    )


async def test_account_http_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Classify account HTTP entitlement failures through the JSON error body."""
    aioclient_mock.get(USERINFO_URL, status=403, json={"error": {"code": "denied"}})
    with pytest.raises(SubscriptionNotEntitledError):
        await _client(hass).async_get_account()


async def test_account_invalid_json(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Treat invalid account JSON as a malformed provider response."""
    aioclient_mock.get(USERINFO_URL, text="not-json")
    with pytest.raises(MalformedProviderResponseError):
        await _client(hass).async_get_account()


async def test_account_http_error_with_unreadable_body(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Classify account HTTP errors even when the body cannot be parsed."""
    aioclient_mock.get(USERINFO_URL, status=401, text="plain")
    with pytest.raises(AuthenticationRejectedError):
        await _client(hass).async_get_account()


async def test_models_sdk_error(hass: HomeAssistant) -> None:
    """Translate SDK failures while listing models."""
    with (
        patch(
            "openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
            side_effect=_status_error(403),
        ),
        pytest.raises(SubscriptionNotEntitledError),
    ):
        await _client(hass).async_get_models()


async def test_async_validate(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Compose account identity and model discovery into one snapshot."""
    aioclient_mock.get(
        USERINFO_URL,
        json={"sub": "account-123", "name": "Home User"},
    )
    page = AsyncModelPage(
        [
            Model(
                id="grok-4.5",
                created=1,
                object="model",
                owned_by="xai",
                completion_text_token_price=1,
            )
        ]
    )
    with patch(
        "openai.resources.models.AsyncModels.list",
        new_callable=AsyncMock,
        return_value=page,
    ):
        snapshot = await _client(hass).async_validate()
    assert snapshot.account.subject == "account-123"
    assert snapshot.has_model("grok-4.5")


async def test_async_validate_checks_subject_before_models(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Fail account mismatch before discovering models for the wrong subject."""
    aioclient_mock.get(
        USERINFO_URL,
        json={"sub": "other-account", "name": "Other"},
    )
    with (
        patch(
            "openai.resources.models.AsyncModels.list",
            new_callable=AsyncMock,
        ) as mock_models,
        pytest.raises(AccountMismatchError),
    ):
        await _client(hass).async_validate(expected_subject="account-123")
    mock_models.assert_not_awaited()


async def test_sdk_client_reuses_and_updates_token(hass: HomeAssistant) -> None:
    """Reuse one SDK client and rotate its API key across requests."""

    class _FakeSDK:
        def __init__(self) -> None:
            self.api_key = "unset"
            self.models = MagicMock()
            self.platform_headers = MagicMock()

    page = AsyncModelPage(
        [
            Model(
                id="grok-4.5",
                created=1,
                object="model",
                owned_by="xai",
                completion_text_token_price=1,
            )
        ]
    )
    provider = MagicMock()
    provider.async_get_access_token = AsyncMock(side_effect=["token-a", "token-b"])
    client = SpaceXAIClient(hass, provider, runtime_session=False)
    sdk = _FakeSDK()
    sdk.models.list = AsyncMock(return_value=page)

    def _build_sdk(**kwargs: object) -> _FakeSDK:
        sdk.api_key = kwargs["api_key"]  # type: ignore[assignment]
        return sdk

    with (
        patch(
            "homeassistant.components.spacexai.client.openai.AsyncOpenAI",
            side_effect=_build_sdk,
        ) as mock_ctor,
        patch.object(hass, "async_add_executor_job", new_callable=AsyncMock),
    ):
        await client.async_get_models()
        assert client._sdk_client is sdk
        assert sdk.api_key == "token-a"
        assert mock_ctor.call_count == 1
        await client.async_get_models()
        assert client._sdk_client is sdk
        assert sdk.api_key == "token-b"
        assert mock_ctor.call_count == 1


async def test_stream_request_options(hass: HomeAssistant) -> None:
    """Use streaming, local history, parallel tools, caching, and explicit limits."""
    stream = EventStream(
        [
            ResponseErrorEvent(
                message="unused",
                sequence_number=0,
                type="error",
            )
        ]
    )
    with patch(
        "openai.resources.responses.AsyncResponses.create",
        new_callable=AsyncMock,
        return_value=stream,
    ) as create:
        returned = await _client(hass).async_stream_response(
            model="grok-4.5",
            input=[],
            tools=[],
            max_output_tokens=2048,
            prompt_cache_key="conversation-id",
        )
    assert returned is stream
    assert create.call_args.kwargs["stream"] is True
    assert create.call_args.kwargs["store"] is False
    assert create.call_args.kwargs["include"] == ["reasoning.encrypted_content"]
    assert create.call_args.kwargs["parallel_tool_calls"] is False
    assert create.call_args.kwargs["prompt_cache_key"] == "conversation-id"
    assert "timeout" not in create.call_args.kwargs
    assert "text" not in create.call_args.kwargs


async def test_stream_create_timeout_is_typed(hass: HomeAssistant) -> None:
    """Translate a TTFB asyncio timeout into RequestTimeoutError."""
    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            new_callable=AsyncMock,
            side_effect=TimeoutError(),
        ),
        pytest.raises(RequestTimeoutError),
    ):
        await _client(hass).async_stream_response(
            model="grok-4.5",
            input=[],
            tools=[],
            max_output_tokens=2048,
            prompt_cache_key="conversation-id",
        )


@pytest.mark.parametrize(
    ("status", "model", "body", "runtime", "operation", "error_type"),
    [
        pytest.param(
            401,
            None,
            {},
            False,
            Operation.RESPONSE,
            AuthenticationRejectedError,
            id="401",
        ),
        pytest.param(
            401,
            None,
            {},
            True,
            Operation.RESPONSE,
            ReauthenticationRequiredError,
            id="runtime-401",
        ),
        pytest.param(
            402, None, {}, False, Operation.RESPONSE, QuotaLimitedError, id="402"
        ),
        pytest.param(
            403,
            None,
            {},
            False,
            Operation.RESPONSE,
            SubscriptionNotEntitledError,
            id="403-response",
        ),
        pytest.param(
            403,
            None,
            {},
            False,
            Operation.MODELS,
            SubscriptionNotEntitledError,
            id="403-models",
        ),
        pytest.param(
            403,
            None,
            {},
            False,
            Operation.ACCOUNT,
            SubscriptionNotEntitledError,
            id="403-account",
        ),
        pytest.param(
            403,
            None,
            {},
            False,
            Operation.REVOCATION,
            PermanentProviderError,
            id="403-revocation",
        ),
        pytest.param(
            403,
            None,
            {"error": {"code": "subscription_required", "message": "inactive"}},
            False,
            Operation.REVOCATION,
            SubscriptionNotEntitledError,
            id="403-revocation-subscription-code",
        ),
        pytest.param(
            403,
            None,
            {"error": {"code": "permission_denied"}},
            False,
            Operation.RESPONSE,
            PermanentProviderError,
            id="403-response-permission-denied",
        ),
        pytest.param(
            403,
            None,
            {
                "error": {
                    "message": "Subscription inactive; account is not entitled",
                }
            },
            False,
            Operation.REVOCATION,
            SubscriptionNotEntitledError,
            id="403-revocation-subscription-message",
        ),
        pytest.param(
            404,
            "grok-4.5",
            {"code": "model"},
            False,
            Operation.RESPONSE,
            ModelNotEntitledError,
            id="404",
        ),
        pytest.param(
            408, None, {}, False, Operation.RESPONSE, RequestTimeoutError, id="408"
        ),
        pytest.param(
            429, None, {}, False, Operation.RESPONSE, RateLimitedError, id="429"
        ),
        pytest.param(
            500, None, {}, False, Operation.RESPONSE, TransientProviderError, id="5xx"
        ),
        pytest.param(
            400,
            None,
            {
                "code": "invalid-argument",
                "error": (
                    "Incorrect API key provided. You can obtain an API key "
                    "from https://console.x.ai."
                ),
            },
            False,
            Operation.RESPONSE,
            AuthenticationRejectedError,
            id="400-credential",
        ),
        pytest.param(
            400,
            None,
            {"code": "invalid_token"},
            False,
            Operation.RESPONSE,
            AuthenticationRejectedError,
            id="400-invalid-token-code",
        ),
        pytest.param(
            400,
            None,
            {"error": {"message": "Incorrect API key provided"}},
            False,
            Operation.RESPONSE,
            AuthenticationRejectedError,
            id="400-nested-error-message",
        ),
        pytest.param(
            400,
            None,
            {"error": 1, "message": "Incorrect API key provided"},
            False,
            Operation.RESPONSE,
            AuthenticationRejectedError,
            id="400-fallback-message",
        ),
        pytest.param(
            400,
            None,
            {
                "code": "invalid-argument",
                "error": "Request mentioned an api key field incorrectly",
            },
            False,
            Operation.RESPONSE,
            PermanentProviderError,
            id="400-bare-api-key-not-credential",
        ),
        pytest.param(
            400,
            None,
            None,
            False,
            Operation.RESPONSE,
            PermanentProviderError,
            id="400-non-mapping-body",
        ),
    ],
)
def test_status_classification(
    hass: HomeAssistant,
    status: int,
    model: str | None,
    body: object,
    runtime: bool,
    operation: Operation,
    error_type: type[SpaceXAIError],
) -> None:
    """Classify provider status families, including runtime reauthentication."""
    error = _client(hass, runtime=runtime).translate_sdk_error(
        _status_error(status, body),
        ErrorContext(operation=operation, model=model),
    )
    assert isinstance(error, error_type)
    assert error.context.operation is operation
    assert error.context.model == model


async def test_revoke(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Send refresh-token revocation data on success."""
    aioclient_mock.post(REVOCATION_URL, status=200)
    await _client(hass).async_revoke("refresh", "client", "secret")
    assert aioclient_mock.mock_calls[0][2]["token"] == "refresh"
    assert aioclient_mock.mock_calls[0][2]["client_secret"] == "secret"


async def test_revoke_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Surface TimeoutError while revoking a refresh token."""
    aioclient_mock.post(REVOCATION_URL, exc=TimeoutError())
    with pytest.raises(RequestTimeoutError):
        await _client(hass).async_revoke("refresh-token", "client-id")


async def test_revoke_http_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Classify revocation HTTP failures."""
    aioclient_mock.post(REVOCATION_URL, status=401)
    with pytest.raises(AuthenticationRejectedError):
        await _client(hass).async_revoke("refresh-token", "client-id")


async def test_revoke_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Surface connection failures while revoking a refresh token."""
    aioclient_mock.post(REVOCATION_URL, exc=ClientConnectionError())
    with pytest.raises(ConnectionFailureError):
        await _client(hass).async_revoke("refresh-token", "client-id")


@pytest.mark.parametrize(
    ("err", "error_type"),
    [
        pytest.param(
            APITimeoutError(request=httpx.Request("GET", "https://api.x.ai/v1")),
            RequestTimeoutError,
            id="timeout",
        ),
        pytest.param(
            APIConnectionError(request=httpx.Request("GET", "https://api.x.ai/v1")),
            ConnectionFailureError,
            id="connection",
        ),
        pytest.param(OpenAIError("denied"), PermanentProviderError, id="generic"),
    ],
)
def test_translate_non_status_sdk_errors(
    hass: HomeAssistant,
    err: Exception,
    error_type: type[SpaceXAIError],
) -> None:
    """Translate non-status SDK failures at the client boundary."""
    assert isinstance(
        _client(hass).translate_sdk_error(
            err, ErrorContext(operation=Operation.RESPONSE)
        ),
        error_type,
    )


def test_provider_error_helpers_accept_non_mapping_bodies(hass: HomeAssistant) -> None:
    """Ignore non-mapping provider bodies while classifying failures."""
    error = _client(hass).translate_sdk_error(
        _status_error(400, "not-a-mapping"),
        ErrorContext(operation=Operation.RESPONSE),
    )
    assert isinstance(error, PermanentProviderError)


def test_subscription_and_permission_denial_helpers() -> None:
    """Keep body/code helpers tight for subscription vs permission 403s."""
    assert not _is_subscription_denial(400, None, None)
    assert _is_subscription_denial(
        403, None, {"error": {"message": "Subscription required for access"}}
    )
    assert _is_permission_denial(
        None, {"error": {"message": "Permission denied for this resource"}}
    )


async def test_safe_json_returns_none_on_decode_error() -> None:
    """Ignore unreadable error bodies while classifying HTTP failures."""
    response = AsyncMock()
    response.json = AsyncMock(side_effect=ValueError("bad json"))
    assert await _safe_json(response) is None


async def test_sdk_schema_violation_is_malformed(hass: HomeAssistant) -> None:
    """Treat an SDK schema violation on create as a malformed provider response."""
    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            new_callable=AsyncMock,
            side_effect=ValidationError.from_exception_data("Response", []),
        ),
        pytest.raises(MalformedProviderResponseError),
    ):
        await _client(hass).async_stream_response(
            model="grok-4.5",
            input=[],
            tools=[],
            max_output_tokens=2048,
            prompt_cache_key="conversation-id",
        )


def test_error_category_values_match_translation_keys() -> None:
    """Ensure every closed error category value is a strings.json exception key."""
    assert {category.value for category in ErrorCategory} == {
        "authentication_rejected",
        "refresh_rejected",
        "reauthentication_required",
        "account_mismatch",
        "subscription_not_entitled",
        "no_conversation_models",
        "model_not_entitled",
        "rate_limited",
        "quota_limited",
        "timeout",
        "connection_failure",
        "transient_provider_failure",
        "malformed_provider_response",
        "invalid_model_tool_request",
        "home_assistant_tool_failure",
        "tool_loop_limit",
        "output_limit",
        "permanent_provider_failure",
    }
