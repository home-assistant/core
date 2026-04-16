"""Tests for the Cloudflare Workers AI client wrapper."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from cloudflare import APIConnectionError, AuthenticationError
import httpx
import pytest

from homeassistant.components.cloudflare_ai.client import (
    CloudflareAIAuthError,
    CloudflareAIClient,
    CloudflareAIConnectionError,
    CloudflareAIError,
)
from homeassistant.components.cloudflare_ai.const import CF_AI_GATEWAY_BASE


def _mock_cf() -> MagicMock:
    """Create a mock AsyncCloudflare instance."""
    cf = MagicMock()
    cf.ai = MagicMock()
    cf.ai.run = AsyncMock()
    cf.ai.with_raw_response = MagicMock()
    cf.ai.with_raw_response.run = AsyncMock()
    cf.ai.with_streaming_response = MagicMock()
    cf.ai.models = MagicMock()
    cf.ai.models.list = AsyncMock()
    return cf


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Create a mock httpx AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def mock_cf() -> MagicMock:
    """Create a mock AsyncCloudflare."""
    return _mock_cf()


@pytest.fixture
def client_direct(
    mock_cf: MagicMock, mock_httpx_client: AsyncMock
) -> CloudflareAIClient:
    """Create a direct API client."""
    return CloudflareAIClient(
        cf=mock_cf,
        httpx_client=mock_httpx_client,
        account_id="test_account",
        api_token="test_token",
    )


@pytest.fixture
def client_gateway(
    mock_cf: MagicMock, mock_httpx_client: AsyncMock
) -> CloudflareAIClient:
    """Create an AI Gateway client."""
    return CloudflareAIClient(
        cf=mock_cf,
        httpx_client=mock_httpx_client,
        account_id="test_account",
        api_token="test_token",
        gateway_id="my-gateway",
        gateway_api_token="gw_token",
    )


def _make_response(
    status_code: int = 200,
    json_data: dict | None = None,
    content: bytes = b"",
    content_type: str = "application/json",
) -> MagicMock:
    """Create a mock httpx Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = {"content-type": content_type}
    if json_data is not None:
        resp.json.return_value = json_data
        resp.content = json.dumps(json_data).encode()
    else:
        resp.content = content
    resp.text = content.decode("utf-8", errors="replace") if content else ""
    return resp


def _make_auth_error() -> AuthenticationError:
    """Create an AuthenticationError instance."""
    return AuthenticationError.__new__(AuthenticationError)


def _make_connection_error() -> APIConnectionError:
    """Create an APIConnectionError instance."""
    return APIConnectionError.__new__(APIConnectionError)


async def _async_iter(items: list[Any]) -> Any:
    """Helper to make an async iterator from a list."""
    for item in items:
        yield item


class TestURLConstruction:
    """Test URL construction for gateway."""

    def test_gateway_url(self, client_gateway: CloudflareAIClient) -> None:
        """Test gateway URL is constructed correctly."""
        url = client_gateway._gateway_url("@cf/meta/llama-3.3-70b")
        assert url == (
            f"{CF_AI_GATEWAY_BASE}/test_account"
            "/my-gateway/workers-ai/@cf/meta/llama-3.3-70b"
        )

    def test_use_gateway_flag(
        self,
        client_direct: CloudflareAIClient,
        client_gateway: CloudflareAIClient,
    ) -> None:
        """Test use_gateway property."""
        assert client_direct.use_gateway is False
        assert client_gateway.use_gateway is True

    def test_use_gateway_with_empty_id(
        self, mock_cf: MagicMock, mock_httpx_client: AsyncMock
    ) -> None:
        """Test that empty gateway_id is treated as not configured."""
        client = CloudflareAIClient(
            cf=mock_cf,
            httpx_client=mock_httpx_client,
            account_id="test",
            api_token="token",
            gateway_id="",
        )
        assert client.use_gateway is False


class TestDirectAPI:
    """Test direct API calls via SDK."""

    async def test_run_model_calls_sdk(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test run_model delegates to cf.ai.run for direct API."""
        mock_cf.ai.run.return_value = {"response": "hello"}
        result = await client_direct.run_model(
            "@cf/test/model",
            {"messages": [{"role": "user", "content": "hi"}]},
        )
        assert result == {"response": "hello"}
        mock_cf.ai.run.assert_called_once()

    async def test_run_model_unwraps_non_dict(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test non-dict SDK results are wrapped."""
        mock_cf.ai.run.return_value = "plain text"
        result = await client_direct.run_model("@cf/test/model", {})
        assert result == {"response": "plain text"}

    async def test_run_model_none_result(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test None result becomes empty response."""
        mock_cf.ai.run.return_value = None
        result = await client_direct.run_model("@cf/test/model", {})
        assert result == {"response": ""}

    async def test_run_model_auth_error(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test SDK AuthenticationError is converted to CloudflareAIAuthError."""
        mock_cf.ai.run.side_effect = _make_auth_error()
        with pytest.raises(CloudflareAIAuthError):
            await client_direct.run_model("@cf/test/model", {})

    async def test_run_model_connection_error(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test APIConnectionError is converted to CloudflareAIConnectionError."""
        mock_cf.ai.run.side_effect = _make_connection_error()
        with pytest.raises(CloudflareAIConnectionError):
            await client_direct.run_model("@cf/test/model", {})

    async def test_run_model_extra_body(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test that unknown params are passed via extra_body."""
        mock_cf.ai.run.return_value = {"response": "ok"}
        await client_direct.run_model(
            "@cf/test/model",
            {"messages": [], "custom_param": "value"},
        )
        call_kwargs = mock_cf.ai.run.call_args[1]
        assert call_kwargs.get("messages") == []
        assert call_kwargs.get("extra_body") == {"custom_param": "value"}

    async def test_run_model_no_extra_body(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test that extra_body is not added when all params are SDK-known."""
        mock_cf.ai.run.return_value = {"response": "ok"}
        await client_direct.run_model(
            "@cf/test/model",
            {"messages": [], "max_tokens": 100},
        )
        call_kwargs = mock_cf.ai.run.call_args[1]
        assert "extra_body" not in call_kwargs


class TestGatewayAPI:
    """Test AI Gateway calls via httpx client."""

    async def test_gateway_json(
        self,
        client_gateway: CloudflareAIClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test gateway calls use httpx_client.post with gateway URL."""
        mock_httpx_client.post = AsyncMock(
            return_value=_make_response(
                json_data={
                    "result": {"response": "hello"},
                    "success": True,
                }
            )
        )
        result = await client_gateway.run_model("@cf/test/model", {"messages": []})
        assert result == {"response": "hello"}
        call_url = mock_httpx_client.post.call_args[0][0]
        assert "gateway.ai.cloudflare.com" in call_url
        assert "my-gateway" in call_url

    async def test_gateway_auth_headers(
        self,
        client_gateway: CloudflareAIClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test gateway calls include cf-aig-authorization header."""
        mock_httpx_client.post = AsyncMock(
            return_value=_make_response(json_data={"response": "ok"})
        )
        await client_gateway.run_model("@cf/test/model", {})
        headers = mock_httpx_client.post.call_args[1]["headers"]
        assert headers["cf-aig-authorization"] == "Bearer gw_token"
        assert headers["Authorization"] == "Bearer test_token"

    async def test_gateway_auth_error(
        self,
        client_gateway: CloudflareAIClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test 401 from gateway raises auth error."""
        mock_httpx_client.post = AsyncMock(return_value=_make_response(status_code=401))
        with pytest.raises(CloudflareAIAuthError):
            await client_gateway.run_model("@cf/test/model", {})

    async def test_gateway_500_error(
        self,
        client_gateway: CloudflareAIClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test 500 from gateway raises generic error."""
        mock_httpx_client.post = AsyncMock(return_value=_make_response(status_code=500))
        with pytest.raises(CloudflareAIError):
            await client_gateway.run_model("@cf/test/model", {})


class TestStreamModel:
    """Test streaming via SDK and gateway."""

    async def test_stream_sdk(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test streaming via SDK yields parsed events."""
        # Mock the SDK streaming context manager
        mock_response = MagicMock()

        async def mock_iter_lines() -> Any:
            for line in (
                'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                'data: {"choices":[{"delta":{"content":" world"}}]}',
                "data: [DONE]",
            ):
                yield line

        mock_response.iter_lines = mock_iter_lines

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_cf.ai.with_streaming_response.run = MagicMock(return_value=mock_ctx)

        events = [
            event
            async for event in client_direct.stream_model(
                "@cf/test/model", {"messages": []}
            )
        ]
        assert len(events) == 2
        assert events[0]["choices"][0]["delta"]["content"] == "Hello"

    async def test_stream_sdk_skips_invalid_json(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test streaming skips lines that aren't valid JSON."""
        mock_response = MagicMock()

        async def mock_iter_lines() -> Any:
            for line in (
                "data: invalid json",
                'data: {"valid": true}',
                "data: [DONE]",
            ):
                yield line

        mock_response.iter_lines = mock_iter_lines
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_cf.ai.with_streaming_response.run = MagicMock(return_value=mock_ctx)

        events = [
            event async for event in client_direct.stream_model("@cf/test/model", {})
        ]
        assert events == [{"valid": True}]

    async def test_stream_sdk_skips_non_data_lines(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test streaming skips lines not starting with 'data: '."""
        mock_response = MagicMock()

        async def mock_iter_lines() -> Any:
            for line in (
                "",
                "id: 1",
                'data: {"event": 1}',
                "data: [DONE]",
            ):
                yield line

        mock_response.iter_lines = mock_iter_lines
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_cf.ai.with_streaming_response.run = MagicMock(return_value=mock_ctx)

        events = [
            event async for event in client_direct.stream_model("@cf/test/model", {})
        ]
        assert events == [{"event": 1}]

    async def test_stream_sdk_extra_body(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test streaming passes unknown params via extra_body."""
        mock_response = MagicMock()

        async def mock_iter_lines() -> Any:
            yield "data: [DONE]"

        mock_response.iter_lines = mock_iter_lines
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_cf.ai.with_streaming_response.run = MagicMock(return_value=mock_ctx)

        async for _ in client_direct.stream_model(
            "@cf/test/model",
            {"messages": [], "stream": True, "custom": "x"},
        ):
            pass
        call_kwargs = mock_cf.ai.with_streaming_response.run.call_args[1]
        assert call_kwargs.get("stream") is True
        assert call_kwargs.get("extra_body") == {"custom": "x"}

    async def test_stream_auth_error(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test stream auth errors are wrapped."""
        mock_cf.ai.with_streaming_response.run = MagicMock(
            side_effect=_make_auth_error()
        )
        with pytest.raises(CloudflareAIAuthError):
            async for _ in client_direct.stream_model("@cf/test/model", {}):
                pass

    async def test_stream_connection_error(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test stream connection errors are wrapped."""
        mock_cf.ai.with_streaming_response.run = MagicMock(
            side_effect=_make_connection_error()
        )
        with pytest.raises(CloudflareAIConnectionError):
            async for _ in client_direct.stream_model("@cf/test/model", {}):
                pass

    async def test_stream_generic_exception(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test stream wraps unexpected exceptions."""
        mock_cf.ai.with_streaming_response.run = MagicMock(
            side_effect=RuntimeError("oops")
        )
        with pytest.raises(CloudflareAIError):
            async for _ in client_direct.stream_model("@cf/test/model", {}):
                pass

    async def test_stream_gateway(
        self,
        client_gateway: CloudflareAIClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test streaming via gateway."""
        mock_response = _make_response(status_code=200)

        async def mock_aiter_lines() -> Any:
            for line in (
                'data: {"event": "first"}',
                "data: [DONE]",
                'data: {"event": "after"}',
            ):
                yield line

        mock_response.aiter_lines = mock_aiter_lines
        mock_response.aclose = AsyncMock()

        mock_httpx_client.build_request = MagicMock(return_value=MagicMock())
        mock_httpx_client.send = AsyncMock(return_value=mock_response)

        events = [
            event
            async for event in client_gateway.stream_model(
                "@cf/test/model", {"messages": []}
            )
        ]
        # [DONE] terminates iteration, so only the first event is collected
        assert events == [{"event": "first"}]

    async def test_stream_gateway_auth_error(
        self,
        client_gateway: CloudflareAIClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test gateway streaming 401 raises auth error."""
        mock_response = _make_response(status_code=401)
        mock_response.aclose = AsyncMock()
        mock_httpx_client.build_request = MagicMock(return_value=MagicMock())
        mock_httpx_client.send = AsyncMock(return_value=mock_response)

        with pytest.raises(CloudflareAIAuthError):
            async for _ in client_gateway.stream_model("@cf/test/model", {}):
                pass


class TestValidateCredentials:
    """Test credential validation."""

    async def test_validate_success(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test successful credential validation."""
        mock_cf.ai.models.list = AsyncMock(return_value=[])
        result = await client_direct.validate_credentials()
        assert result is True

    async def test_validate_auth_error(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test auth error during validation."""
        mock_cf.ai.models.list = AsyncMock(side_effect=_make_auth_error())
        with pytest.raises(CloudflareAIAuthError):
            await client_direct.validate_credentials()

    async def test_validate_connection_error(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test connection error during validation."""
        mock_cf.ai.models.list = AsyncMock(side_effect=_make_connection_error())
        with pytest.raises(CloudflareAIConnectionError):
            await client_direct.validate_credentials()

    async def test_validate_generic_error(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test generic error during validation is wrapped as connection error."""
        mock_cf.ai.models.list = AsyncMock(side_effect=RuntimeError("network"))
        with pytest.raises(CloudflareAIConnectionError):
            await client_direct.validate_credentials()


class TestEnvelopeUnwrap:
    """Test CF API response envelope unwrapping."""

    def test_unwrap_envelope(self) -> None:
        """Test envelope with result and success keys is unwrapped."""
        result = CloudflareAIClient._unwrap(
            {"result": {"response": "hello"}, "success": True}
        )
        assert result == {"response": "hello"}

    def test_no_unwrap_without_success(self) -> None:
        """Test response without success key is not unwrapped."""
        data = {"response": "hello", "tool_calls": []}
        result = CloudflareAIClient._unwrap(data)
        assert result == data

    def test_no_unwrap_without_result(self) -> None:
        """Test response without result key is not unwrapped."""
        data = {"success": True, "data": "x"}
        result = CloudflareAIClient._unwrap(data)
        assert result == data


class TestCheckHttp:
    """Test HTTP response checking."""

    def test_check_http_401(self) -> None:
        """Test 401 raises auth error."""
        resp = _make_response(status_code=401)
        with pytest.raises(CloudflareAIAuthError, match="Authentication failed"):
            CloudflareAIClient._check_http(resp)

    def test_check_http_403(self) -> None:
        """Test 403 raises auth error."""
        resp = _make_response(status_code=403)
        with pytest.raises(CloudflareAIAuthError, match="Insufficient permissions"):
            CloudflareAIClient._check_http(resp)

    def test_check_http_400(self) -> None:
        """Test 400 raises generic error."""
        resp = _make_response(status_code=400)
        with pytest.raises(CloudflareAIError, match="API error 400"):
            CloudflareAIClient._check_http(resp)

    def test_check_http_500(self) -> None:
        """Test 500 raises generic error."""
        resp = _make_response(status_code=500)
        with pytest.raises(CloudflareAIError, match="API error 500"):
            CloudflareAIClient._check_http(resp)

    def test_check_http_200_ok(self) -> None:
        """Test 200 does not raise."""
        resp = _make_response(status_code=200)
        CloudflareAIClient._check_http(resp)

    def test_check_http_204_no_content(self) -> None:
        """Test 204 does not raise."""
        resp = _make_response(status_code=204)
        CloudflareAIClient._check_http(resp)


class TestGatewayHeaders:
    """Test gateway header construction."""

    def test_gateway_headers_with_token(
        self, client_gateway: CloudflareAIClient
    ) -> None:
        """Test headers include gateway token when set."""
        headers = client_gateway._gateway_headers()
        assert headers["cf-aig-authorization"] == "Bearer gw_token"
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Content-Type"] == "application/json"

    def test_gateway_headers_fallback_to_api_token(
        self, mock_cf: MagicMock, mock_httpx_client: AsyncMock
    ) -> None:
        """Test headers fall back to API token when gateway token is empty."""
        client = CloudflareAIClient(
            cf=mock_cf,
            httpx_client=mock_httpx_client,
            account_id="test",
            api_token="main_token",
            gateway_id="gw",
            gateway_api_token="",
        )
        headers = client._gateway_headers()
        assert headers["cf-aig-authorization"] == "Bearer main_token"

    def test_gateway_headers_fallback_when_none(
        self, mock_cf: MagicMock, mock_httpx_client: AsyncMock
    ) -> None:
        """Test headers fall back to API token when gateway token is None."""
        client = CloudflareAIClient(
            cf=mock_cf,
            httpx_client=mock_httpx_client,
            account_id="test",
            api_token="main_token",
            gateway_id="gw",
            gateway_api_token=None,
        )
        headers = client._gateway_headers()
        assert headers["cf-aig-authorization"] == "Bearer main_token"


class TestRunModelExceptionWrapping:
    """Test that run_model wraps unexpected exceptions."""

    async def test_run_model_wraps_generic_exception(
        self, client_direct: CloudflareAIClient, mock_cf: MagicMock
    ) -> None:
        """Test unexpected exceptions are wrapped as CloudflareAIError."""
        mock_cf.ai.run.side_effect = RuntimeError("something broke")
        with pytest.raises(CloudflareAIError, match="something broke"):
            await client_direct.run_model("@cf/test/model", {})

    async def test_run_model_passes_through_cf_error(
        self, client_gateway: CloudflareAIClient, mock_httpx_client: AsyncMock
    ) -> None:
        """Test that CloudflareAIError raised in gateway path is re-raised."""
        # _check_http raises CloudflareAIError on 500, run_model should pass it through
        mock_httpx_client.post = AsyncMock(return_value=_make_response(status_code=500))
        with pytest.raises(CloudflareAIError):
            await client_gateway.run_model("@cf/test/model", {})
