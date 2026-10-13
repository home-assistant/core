"""Test the Sign in with ChatGPT authentication helpers."""

import asyncio
from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qsl, urlparse

import httpx2
import openai
import pytest

from homeassistant.components.openai_conversation.chatgpt_auth import (
    AUTHORIZE_URL,
    CLIENT_ID_PREFIX,
    DYNAMIC_AGENT_CLIENT,
    MODELS_URL,
    PLAN_SCOPE,
    REDIRECT_URI,
    RESOURCE,
    SCOPE,
    SUBSCRIPTION_INFERENCE_ERROR_HINTS,
    TOKEN_URL,
    ChatGPTAuth,
    ChatGPTSubscriptionClient,
    async_get_agent_host_id,
    async_get_jwks,
    async_get_subscription_models,
    async_get_subscription_models_for_credentials,
    async_token_request,
    async_validate_id_token,
    create_authorization_request,
    credentials_from_token,
    parse_callback_url,
    shape_request_for_subscription,
    subscription_error_message,
)
from homeassistant.components.openai_conversation.const import (
    AUTH_METHOD_CHATGPT,
    CONF_AUTH_METHOD,
    CONF_EXT_AGENT_HOST_ID,
    CONF_ID_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_SCOPES,
    CONF_SUB,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.components.openai_conversation import (
    create_chatgpt_id_token,
    create_chatgpt_jwks,
    create_chatgpt_rsa_key,
)

CLIENT_ID = f"{CLIENT_ID_PREFIX}abc123"
HOST_ID = "urn:uuid:00000000-0000-4000-8000-000000000000"


def _response(status_code: int = 200, json_data: Any = None) -> MagicMock:
    """Create a mocked httpx response."""
    response = MagicMock()
    response.status_code = status_code
    if json_data is None:
        response.json = MagicMock(side_effect=ValueError)
    else:
        response.json = MagicMock(return_value=json_data)
    return response


@pytest.fixture
def mock_http_client() -> Generator[MagicMock]:
    """Patch the shared httpx client used by the SIWC helpers."""
    client = MagicMock()
    client.post = AsyncMock()
    client.get = AsyncMock()
    with patch(
        "homeassistant.components.openai_conversation.chatgpt_auth.get_async_client",
        return_value=client,
    ):
        yield client


def _token_response(**kwargs: Any) -> dict[str, Any]:
    """Create a token endpoint response body."""
    token = {
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "id_token": "id-1",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": f"{PLAN_SCOPE} email offline_access openid profile resource.invoke",
    }
    token.update(kwargs)
    return token


def _chatgpt_entry(hass: HomeAssistant, **data: Any) -> MockConfigEntry:
    """Create a config entry which signs in with ChatGPT."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="ChatGPT subscription",
        unique_id=f"{CONF_SUB}-value:{CLIENT_ID}",
        version=2,
        minor_version=7,
        data={
            CONF_AUTH_METHOD: AUTH_METHOD_CHATGPT,
            "client_id": CLIENT_ID,
            CONF_EXT_AGENT_HOST_ID: HOST_ID,
            CONF_SUB: "sub-value",
            CONF_ACCESS_TOKEN: "access-old",
            CONF_REFRESH_TOKEN: "refresh-old",
            CONF_ID_TOKEN: "id-old",
            "expires_at": (dt_util.utcnow() + timedelta(hours=1)).isoformat(),
            CONF_SCOPES: [PLAN_SCOPE],
            **data,
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_authorization_request_registration() -> None:
    """Test the first authorization request registers a dynamic client."""
    request = create_authorization_request(client_id=None, ext_agent_host_id=HOST_ID)

    assert request.url.startswith(f"{AUTHORIZE_URL}?")
    assert request.registration
    assert request.client_id == DYNAMIC_AGENT_CLIENT
    assert request.redirect_uri == REDIRECT_URI

    params = dict(parse_qsl(urlparse(request.url).query))
    assert params == {
        "response_type": "code",
        "client_id": DYNAMIC_AGENT_CLIENT,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "resource": RESOURCE,
        "state": request.state,
        "nonce": request.nonce,
        "code_challenge": params["code_challenge"],
        "code_challenge_method": "S256",
        "ext_agent_host_id": HOST_ID,
        "agent_name_hint": "Home Assistant",
    }
    assert params["code_challenge"] != request.code_verifier
    assert "=" not in params["code_challenge"]


async def test_authorization_request_reauthorization() -> None:
    """Test a returning sign in reuses the issued client id."""
    request = create_authorization_request(
        client_id=CLIENT_ID,
        ext_agent_host_id=HOST_ID,
        id_token_hint="retained-id-token",
    )

    assert not request.registration
    assert request.client_id == CLIENT_ID

    params = dict(parse_qsl(urlparse(request.url).query))
    assert params["client_id"] == CLIENT_ID
    assert params["id_token_hint"] == "retained-id-token"
    # agent_name_hint is only sent for the initial registration.
    assert "agent_name_hint" not in params


def test_parse_callback_url() -> None:
    """Test parsing of the URL the browser ended up on."""
    url = (
        f"{REDIRECT_URI}?code=the-code&scope=chatgpt.tokens.use.direct+email"
        f"&state=the-state&client_id={CLIENT_ID}"
    )
    assert parse_callback_url(url) == {
        "code": "the-code",
        "scope": "chatgpt.tokens.use.direct email",
        "state": "the-state",
        "client_id": CLIENT_ID,
    }


async def test_token_request_success(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test a successful token endpoint request."""
    mock_http_client.post.return_value = _response(200, _token_response())

    assert await async_token_request(hass, {"grant_type": "refresh_token"}) == (
        _token_response()
    )
    assert mock_http_client.post.call_args.args[0] == TOKEN_URL


@pytest.mark.parametrize(
    "error",
    [
        "invalid_grant",
        "invalid_refresh_token",
        "token_expired",
        "refresh_token_expired",
        "refresh_token_invalidated",
        "refresh_token_reused",
        "invalid_client",
    ],
)
async def test_token_request_fatal_errors(
    hass: HomeAssistant, mock_http_client: MagicMock, error: str
) -> None:
    """Test errors which invalidate the refresh token."""
    mock_http_client.post.return_value = _response(400, {"error": error})

    with pytest.raises(ConfigEntryAuthFailed):
        await async_token_request(
            hass, {"grant_type": "refresh_token"}, fatal_errors=True
        )

    # Without fatal_errors the caller has to recover itself.
    with pytest.raises(HomeAssistantError):
        await async_token_request(hass, {"grant_type": "refresh_token"})


async def test_token_request_connection_error(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test a connection error while talking to the token endpoint."""
    mock_http_client.post.side_effect = httpx2.ConnectError("boom")

    with pytest.raises(HomeAssistantError):
        await async_token_request(hass, {"grant_type": "refresh_token"})


def _jwks_and_token(
    *, client_id: str = CLIENT_ID, nonce: str = "nonce-1", **claims: Any
) -> tuple[dict[str, Any], str]:
    """Create a JWKS document and a matching signed ID token."""
    private_key = create_chatgpt_rsa_key()
    token = create_chatgpt_id_token(
        private_key, client_id=client_id, nonce=nonce, **claims
    )
    return create_chatgpt_jwks(private_key), token


async def test_validate_id_token(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test ID token validation against the JWKS."""
    jwks, token = _jwks_and_token(nonce="nonce-1")
    mock_http_client.get.return_value = _response(200, jwks)

    claims = await async_validate_id_token(
        hass, token, client_id=CLIENT_ID, nonce="nonce-1"
    )

    assert claims["sub"] == "chatgpt-user-1"
    assert claims["email"] == "user@example.com"


@pytest.mark.parametrize(
    ("client_id", "nonce"),
    [
        ("oaiapp_other", "nonce-1"),
        (CLIENT_ID, "nonce-other"),
    ],
)
async def test_validate_id_token_rejects(
    hass: HomeAssistant,
    mock_http_client: MagicMock,
    client_id: str,
    nonce: str,
) -> None:
    """Test that a wrong audience or nonce is rejected."""
    jwks, token = _jwks_and_token(client_id=CLIENT_ID, nonce="nonce-1")
    mock_http_client.get.return_value = _response(200, jwks)

    with pytest.raises(HomeAssistantError):
        await async_validate_id_token(hass, token, client_id=client_id, nonce=nonce)


async def test_validate_id_token_expired(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that an expired ID token is rejected."""
    jwks, token = _jwks_and_token(exp=int(dt_util.utcnow().timestamp()) - 60)
    mock_http_client.get.return_value = _response(200, jwks)

    with pytest.raises(HomeAssistantError):
        await async_validate_id_token(hass, token, client_id=CLIENT_ID, nonce="nonce-1")


async def test_access_token_is_refreshed_before_expiry(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that an expiring access token is refreshed and persisted."""
    entry = _chatgpt_entry(
        hass, expires_at=(dt_util.utcnow() - timedelta(seconds=1)).isoformat()
    )
    mock_http_client.post.return_value = _response(
        200,
        _token_response(
            access_token="access-2", refresh_token="refresh-2", id_token="id-2"
        ),
    )

    auth = ChatGPTAuth.from_entry(hass, entry)

    assert await auth.async_get_access_token() == "access-2"
    # The refresh token rotates on every refresh.
    assert entry.data[CONF_REFRESH_TOKEN] == "refresh-2"
    assert entry.data[CONF_ACCESS_TOKEN] == "access-2"
    assert entry.data[CONF_ID_TOKEN] == "id-2"
    assert mock_http_client.post.call_args.kwargs["data"] == {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": "refresh-old",
        "resource": RESOURCE,
    }


async def test_access_token_not_refreshed_while_valid(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that a valid access token is reused."""
    entry = _chatgpt_entry(hass)
    auth = ChatGPTAuth.from_entry(hass, entry)

    assert await auth.async_get_access_token() == "access-old"
    assert mock_http_client.post.call_count == 0


async def test_access_token_respects_earliest_refresh_at(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that the token endpoint is not polled before earliest_refresh_at."""
    entry = _chatgpt_entry(
        hass,
        expires_at=(dt_util.utcnow() - timedelta(seconds=1)).isoformat(),
        earliest_refresh_at=(dt_util.utcnow() + timedelta(minutes=5)).isoformat(),
    )
    auth = ChatGPTAuth.from_entry(hass, entry)

    assert await auth.async_get_access_token() == "access-old"
    assert mock_http_client.post.call_count == 0


async def test_concurrent_requests_refresh_once(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that concurrent requests only refresh the token once."""
    entry = _chatgpt_entry(
        hass, expires_at=(dt_util.utcnow() - timedelta(seconds=1)).isoformat()
    )
    mock_http_client.post.return_value = _response(
        200, _token_response(access_token="access-2", refresh_token="refresh-2")
    )
    auth = ChatGPTAuth.from_entry(hass, entry)

    await asyncio.gather(
        auth.async_get_access_token(),
        auth.async_get_access_token(),
        auth.async_get_access_token(),
    )

    assert mock_http_client.post.call_count == 1


async def test_refresh_failure_starts_reauth(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that a dead refresh token raises and starts the reauth flow."""
    entry = _chatgpt_entry(
        hass, expires_at=(dt_util.utcnow() - timedelta(seconds=1)).isoformat()
    )
    mock_http_client.post.return_value = _response(400, {"error": "invalid_grant"})
    auth = ChatGPTAuth.from_entry(hass, entry)

    with pytest.raises(ConfigEntryAuthFailed):
        await auth.async_get_access_token()

    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_authentication_error_forces_refresh(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that a rejected access token is refreshed even when not expired."""
    entry = _chatgpt_entry(hass)
    mock_http_client.post.return_value = _response(
        200, _token_response(access_token="access-2", refresh_token="refresh-2")
    )
    auth = ChatGPTAuth.from_entry(hass, entry)

    await auth.async_handle_authentication_error()

    assert entry.data[CONF_ACCESS_TOKEN] == "access-2"


async def test_subscription_client_custom_auth(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that the subscription client attaches and retries the token."""
    entry = _chatgpt_entry(hass)
    http_client = httpx2.AsyncClient()
    try:
        client = ChatGPTSubscriptionClient(
            ChatGPTAuth.from_entry(hass, entry), http_client=http_client
        )
        auth = client.custom_auth
        assert auth is not None

        request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
        flow = auth.async_auth_flow(request)
        sent = await anext(flow)
        assert sent.headers["Authorization"] == "Bearer access-old"

        # A 401 refreshes the token and replays the request once.
        mock_http_client.post.return_value = _response(
            200, _token_response(access_token="access-2", refresh_token="refresh-2")
        )
        retried = await flow.asend(_response(401))
        assert retried.headers["Authorization"] == "Bearer access-2"
        with pytest.raises(StopAsyncIteration):
            await flow.asend(_response(200))
    finally:
        await http_client.aclose()


async def test_subscription_client_request_carries_access_token(
    hass: HomeAssistant,
) -> None:
    """Test that a request through the client authenticates with the plan token."""
    entry = _chatgpt_entry(hass)
    seen: dict[str, str | None] = {}

    async def handler(request: httpx2.Request) -> httpx2.Response:
        seen["authorization"] = request.headers.get("authorization")
        return httpx2.Response(200, json={"object": "list", "data": []})

    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    client = ChatGPTSubscriptionClient(
        ChatGPTAuth.from_entry(hass, entry), http_client=http_client
    )
    try:
        models = await client.with_options(timeout=10.0).models.list()
    finally:
        await http_client.aclose()

    assert models.object == "list"
    # A placeholder API key must never reach the wire.
    assert seen["authorization"] == "Bearer access-old"


async def test_credentials_roundtrip() -> None:
    """Test that credentials survive a config entry round trip."""
    token = _token_response(earliest_refresh_at="2030-01-01T00:00:00+00:00")
    credentials = credentials_from_token(
        token,
        client_id=CLIENT_ID,
        ext_agent_host_id=HOST_ID,
        sub="chatgpt-user-1",
        email="user@example.com",
    )

    assert credentials.unique_id == f"chatgpt-user-1:{CLIENT_ID}"
    assert credentials.scopes == [
        PLAN_SCOPE,
        "email",
        "offline_access",
        "openid",
        "profile",
        "resource.invoke",
    ]

    entry_data = credentials.as_entry_data()
    assert entry_data[CONF_AUTH_METHOD] == AUTH_METHOD_CHATGPT
    assert entry_data["client_id"] == CLIENT_ID
    assert entry_data[CONF_EXT_AGENT_HOST_ID] == HOST_ID
    assert entry_data["email"] == "user@example.com"

    from_entry = type(credentials).from_entry_data(entry_data)
    assert from_entry == credentials


async def test_refresh_keeps_identity_and_old_refresh_token(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test fields missing from a refresh response are retained."""
    entry = _chatgpt_entry(hass)
    auth = ChatGPTAuth.from_entry(hass, entry)
    mock_http_client.post.return_value = _response(
        200, {"access_token": "access-2", "expires_in": 3600, "scope": ""}
    )

    await auth.async_handle_authentication_error()

    assert auth.credentials.access_token == "access-2"
    assert auth.credentials.refresh_token == "refresh-old"
    assert auth.credentials.id_token == "id-old"
    assert auth.credentials.sub == "sub-value"
    assert auth.credentials.scopes == [PLAN_SCOPE]


def test_shape_request_for_subscription() -> None:
    """Test the request shaping for the subscription route."""
    model_args: dict[str, Any] = {
        "model": "gpt-4o-mini",
        "input": [],
        "max_output_tokens": 3000,
        "safety_identifier": "conv-1",
        "prompt_cache_key": "subentry-1",
        "prompt_cache_retention": "24h",
        "temperature": 1.0,
        "top_p": 1.0,
        "service_tier": "auto",
        "store": True,
        "stream": False,
        "tools": [
            {"type": "function", "name": "turn_on"},
            {"type": "web_search"},
            {"type": "image_generation"},
        ],
        "tool_choice": {"type": "image_generation"},
    }
    messages: list[Any] = [
        {"type": "message", "role": "developer", "content": "You are Home Assistant"},
        {"type": "message", "role": "user", "content": "Turn on the light"},
        {"type": "message", "role": "system", "content": "Stay brief"},
        {"type": "function_call", "name": "turn_on", "arguments": "{}", "call_id": "1"},
    ]

    shape_request_for_subscription(model_args, messages)

    for forbidden in (
        "max_output_tokens",
        "safety_identifier",
        "prompt_cache_key",
        "prompt_cache_retention",
        "temperature",
        "top_p",
        "service_tier",
        "tool_choice",
    ):
        assert forbidden not in model_args

    # The subscription route requires unsaved, streamed responses.
    assert model_args["store"] is False
    assert model_args["stream"] is True
    # System content is sent as instructions instead of an input item.
    assert model_args["instructions"] == "You are Home Assistant"
    # A replayed function call stays flat: the route has no namespaces.
    assert messages == [
        {"type": "message", "role": "user", "content": "Turn on the light"},
        {"type": "message", "role": "developer", "content": "Stay brief"},
        {
            "type": "function_call",
            "name": "turn_on",
            "arguments": "{}",
            "call_id": "1",
        },
    ]
    # Function tools keep their flat shape; the hosted image generation tool is
    # dropped and web search is kept.
    assert model_args["tools"] == [
        {"type": "function", "name": "turn_on"},
        {"type": "web_search"},
    ]
    # Parameters which are supported by both routes are kept.
    assert model_args["model"] == "gpt-4o-mini"


async def test_get_subscription_models(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that the model catalog slugs are returned in order."""
    auth = ChatGPTAuth.from_entry(hass, _chatgpt_entry(hass))
    mock_http_client.get.return_value = _response(
        200,
        {
            "models": [
                {"slug": "gpt-6.1-sol", "title": "Sol"},
                {"slug": "gpt-6-astra"},
                {"no_slug": "ignored"},
            ]
        },
    )

    assert await async_get_subscription_models(hass, auth) == [
        "gpt-6.1-sol",
        "gpt-6-astra",
    ]
    assert mock_http_client.get.call_args.args[0] == MODELS_URL
    assert mock_http_client.get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer access-old"
    }


async def test_get_subscription_models_malformed_body(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that a catalog body without a models list is rejected."""
    auth = ChatGPTAuth.from_entry(hass, _chatgpt_entry(hass))
    mock_http_client.get.return_value = _response(200, {"data": []})

    with pytest.raises(HomeAssistantError):
        await async_get_subscription_models(hass, auth)


async def test_get_subscription_models_http_error(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that a failing catalog request is reported."""
    auth = ChatGPTAuth.from_entry(hass, _chatgpt_entry(hass))
    response = _response(500, {"error": "boom"})
    response.raise_for_status.side_effect = httpx2.HTTPStatusError(
        "boom", request=httpx2.Request("GET", MODELS_URL), response=response
    )
    mock_http_client.get.return_value = response

    with pytest.raises(HomeAssistantError):
        await async_get_subscription_models(hass, auth)


async def test_get_subscription_models_auth_failed(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that a rejected token fails the auth."""
    auth = ChatGPTAuth.from_entry(hass, _chatgpt_entry(hass))
    mock_http_client.get.return_value = _response(401)

    with pytest.raises(ConfigEntryAuthFailed):
        await async_get_subscription_models(hass, auth)


async def test_get_agent_host_id_is_stable(hass: HomeAssistant) -> None:
    """Test the generated host id is reused on the next read."""
    host_id = await async_get_agent_host_id(hass)
    assert host_id.startswith("urn:uuid:")

    # The stored host id is returned instead of a new one being generated.
    assert await async_get_agent_host_id(hass) == host_id


@pytest.mark.parametrize(
    ("body", "code", "message"),
    [
        ({"error": {"code": "code-1", "message": "message-1"}}, "code-1", "message-1"),
        ({"code": "code-2"}, "code-2", "unknown error"),
        ({"error_description": "description-3"}, None, "description-3"),
        ({"error": {"error_description": "description-4"}}, None, "description-4"),
    ],
)
async def test_token_request_error_body_variants(
    hass: HomeAssistant,
    mock_http_client: MagicMock,
    body: Any,
    code: str | None,
    message: str,
) -> None:
    """Test the error code and message of the known token endpoint bodies."""
    mock_http_client.post.return_value = _response(400, body)

    with pytest.raises(HomeAssistantError) as err:
        await async_token_request(hass, {"grant_type": "refresh_token"})

    assert str(err.value) == f"Sign in with ChatGPT failed ({code}): {message}"


async def test_token_request_invalid_json_success(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test a successful status with a non-JSON body is reported."""
    mock_http_client.post.return_value = _response(200)

    with pytest.raises(HomeAssistantError, match="Invalid token response"):
        await async_token_request(hass, {"grant_type": "refresh_token"})


async def test_token_request_error_without_json_body(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test an error status with a non-JSON body falls back to no error code."""
    mock_http_client.post.return_value = _response(500)

    with pytest.raises(HomeAssistantError) as err:
        await async_token_request(
            hass, {"grant_type": "refresh_token"}, fatal_errors=True
        )

    assert str(err.value) == "Sign in with ChatGPT failed (None): unknown error"


async def test_get_jwks_is_cached(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test the JWKS is only fetched once while the cache is valid."""
    jwks = {"keys": []}
    mock_http_client.get.return_value = _response(200, jwks)

    assert await async_get_jwks(hass) == jwks
    assert await async_get_jwks(hass) == jwks
    assert mock_http_client.get.call_count == 1


async def test_get_jwks_connection_error(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test a connection error while fetching the signing keys."""
    mock_http_client.get.side_effect = httpx2.ConnectError("boom")

    with pytest.raises(HomeAssistantError, match="Could not fetch the OpenAI"):
        await async_get_jwks(hass)


async def test_get_jwks_invalid_body(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test an unparsable signing keys body is reported."""
    mock_http_client.get.return_value = _response(200)

    with pytest.raises(HomeAssistantError, match="Could not parse the OpenAI"):
        await async_get_jwks(hass)


async def test_validate_id_token_invalid_signing_keys(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test a malformed JWKS document is reported."""
    private_key = create_chatgpt_rsa_key()
    token = create_chatgpt_id_token(private_key, client_id=CLIENT_ID, nonce="nonce-1")
    mock_http_client.get.return_value = _response(200, {"keys": [{"kty": "unknown"}]})

    with pytest.raises(HomeAssistantError, match="Invalid signing keys"):
        await async_validate_id_token(hass, token, client_id=CLIENT_ID, nonce="nonce-1")


async def test_validate_id_token_invalid_header(hass: HomeAssistant) -> None:
    """Test an unparsable ID token header is reported."""
    with pytest.raises(HomeAssistantError, match="Invalid ID token"):
        await async_validate_id_token(
            hass, "not-a-jwt", client_id=CLIENT_ID, nonce="nonce-1"
        )


async def test_validate_id_token_unknown_kid_refetches(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test a key rotation is followed by one forced JWKS refetch."""
    private_key = create_chatgpt_rsa_key()
    token = create_chatgpt_id_token(
        private_key, client_id=CLIENT_ID, nonce="nonce-1", kid="rotated-kid"
    )
    mock_http_client.get.return_value = _response(200, create_chatgpt_jwks(private_key))

    with pytest.raises(HomeAssistantError, match="Unknown ID token signing key"):
        await async_validate_id_token(hass, token, client_id=CLIENT_ID, nonce="nonce-1")

    # The cached copy did not know the key, so it was fetched again.
    assert mock_http_client.get.call_count == 2


async def test_authentication_error_respects_earliest_refresh_at(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test a rejected token is not refreshed before earliest_refresh_at."""
    entry = _chatgpt_entry(
        hass, earliest_refresh_at=(dt_util.utcnow() + timedelta(minutes=5)).isoformat()
    )
    auth = ChatGPTAuth.from_entry(hass, entry)

    await auth.async_handle_authentication_error()

    assert mock_http_client.post.call_count == 0


async def test_repeated_refresh_failure_starts_reauth_once(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test that a second dead refresh does not start the reauth flow again."""
    entry = _chatgpt_entry(
        hass, expires_at=(dt_util.utcnow() - timedelta(seconds=1)).isoformat()
    )
    mock_http_client.post.return_value = _response(400, {"error": "invalid_grant"})
    auth = ChatGPTAuth.from_entry(hass, entry)

    for _ in range(2):
        with pytest.raises(ConfigEntryAuthFailed):
            await auth.async_get_access_token()

    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_get_subscription_models_for_credentials(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test the catalog of an account which is not stored in an entry."""
    credentials = credentials_from_token(
        _token_response(), client_id=CLIENT_ID, ext_agent_host_id=HOST_ID
    )
    mock_http_client.get.return_value = _response(
        200, {"models": [{"slug": "gpt-6.1-sol"}]}
    )

    assert await async_get_subscription_models_for_credentials(hass, credentials) == [
        "gpt-6.1-sol"
    ]
    assert mock_http_client.get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer access-1"
    }


async def test_get_subscription_models_connection_error(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test a connection error while listing the account models."""
    auth = ChatGPTAuth.from_entry(hass, _chatgpt_entry(hass))
    mock_http_client.get.side_effect = httpx2.ConnectError("boom")

    with pytest.raises(HomeAssistantError, match="Error talking to OpenAI"):
        await async_get_subscription_models(hass, auth)


async def test_get_subscription_models_invalid_json(
    hass: HomeAssistant, mock_http_client: MagicMock
) -> None:
    """Test an unparsable catalog body is reported."""
    auth = ChatGPTAuth.from_entry(hass, _chatgpt_entry(hass))
    mock_http_client.get.return_value = _response(200)

    with pytest.raises(HomeAssistantError, match="Invalid model catalog response"):
        await async_get_subscription_models(hass, auth)


def test_subscription_error_message() -> None:
    """Test the messages of the subscription route inference errors."""
    request = httpx2.Request("POST", "https://api.openai.com/v1/responses")

    known = openai.RateLimitError(
        message="limit",
        response=httpx2.Response(429, request=request),
        body={"code": "subscription_sharing_usage_limit_exceeded"},
    )
    assert (
        subscription_error_message(known)
        == SUBSCRIPTION_INFERENCE_ERROR_HINTS[
            "subscription_sharing_usage_limit_exceeded"
        ]
    )

    # Any other rejected token means the sign in is no longer valid.
    rejected = openai.AuthenticationError(
        message="nope",
        response=httpx2.Response(401, request=request),
        body={"code": "something_else"},
    )
    assert (
        subscription_error_message(rejected)
        == SUBSCRIPTION_INFERENCE_ERROR_HINTS["subscription_sharing_invalid_user"]
    )

    # An unrelated error is not rewritten.
    assert subscription_error_message(openai.OpenAIError("plain")) is None


def test_shape_request_for_subscription_removes_all_tools() -> None:
    """Test the tools argument is dropped when no tool survives."""
    model_args: dict[str, Any] = {
        "tools": [{"type": "image_generation"}, {"type": "code_interpreter"}]
    }

    shape_request_for_subscription(model_args, [])

    assert "tools" not in model_args
