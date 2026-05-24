"""Tests for the Open Responses client."""

from collections.abc import AsyncIterator

import httpx
import pytest

from homeassistant.components.open_responses.client import AsyncOpenResponsesClient
from homeassistant.components.open_responses.exceptions import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    ModelError,
    RateLimitError,
)


class StreamingBody(httpx.AsyncByteStream):
    """Streaming response body for httpx mock transports."""

    def __init__(self, chunks: list[bytes]) -> None:
        """Initialize the stream."""
        self.chunks = chunks

    async def __aiter__(self):
        """Yield stream chunks."""
        for chunk in self.chunks:
            yield chunk


@pytest.fixture
def requests() -> list[httpx.Request]:
    """Collect HTTP requests."""
    return []


@pytest.fixture
async def http_client(
    requests: list[httpx.Request],
) -> AsyncIterator[httpx.AsyncClient]:
    """Return a mock HTTP client."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "resp_1", "output": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        yield client
    finally:
        await client.aclose()


async def test_create_posts_non_streaming_response(
    http_client: httpx.AsyncClient, requests: list[httpx.Request]
) -> None:
    """Test create sends a normalized Open Responses request."""
    client = AsyncOpenResponsesClient(
        "https://provider.example/v1",
        api_key="secret",
        http_client=http_client,
    )

    response = await client.create(
        model="model-a",
        input="hello",
        max_tool_calls=2,
        store=False,
        user="user-1",
        ignored_none=None,
    )

    assert response == {"id": "resp_1", "output": []}
    request = requests[0]
    assert str(request.url) == "https://provider.example/v1/responses"
    assert request.headers["authorization"] == "Bearer secret"
    assert request.headers["content-type"] == "application/json"
    assert request.read() == (
        b'{"model":"model-a","input":"hello","stream":false,'
        b'"max_tool_calls":2,"store":false,"user":"user-1"}'
    )


@pytest.mark.parametrize(
    ("status_code", "body", "exception_cls", "message"),
    [
        (401, {"error": {"message": "bad key"}}, AuthenticationError, "bad key"),
        (429, {"error": "slow down"}, RateLimitError, "slow down"),
        (422, {"message": "bad request"}, BadRequestError, "bad request"),
        (404, {"error": {"code": "missing_model"}}, ModelError, "missing_model"),
        (500, "plain failure", APIStatusError, "plain failure"),
    ],
)
async def test_create_maps_error_statuses(
    status_code: int,
    body: dict[str, object] | str,
    exception_cls: type[APIStatusError],
    message: str,
) -> None:
    """Test status errors map to integration exceptions."""

    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(body, str):
            return httpx.Response(status_code, text=body)
        return httpx.Response(status_code, json=body)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncOpenResponsesClient(
        "https://provider.example",
        http_client=http_client,
    )
    try:
        with pytest.raises(exception_cls) as err:
            await client.create(model="model-a", input="hello")
    finally:
        await http_client.aclose()

    assert str(err.value) == message
    assert err.value.status_code == status_code


async def test_create_maps_connection_errors() -> None:
    """Test connection errors map to integration exceptions."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncOpenResponsesClient(
        "https://provider.example",
        http_client=http_client,
    )
    try:
        with pytest.raises(APIConnectionError) as err:
            await client.create(model="model-a", input="hello")
    finally:
        await http_client.aclose()

    assert "network down" in str(err.value)
    assert isinstance(err.value.__cause__, httpx.ConnectError)


async def test_create_streams_sse_events(requests: list[httpx.Request]) -> None:
    """Test streaming responses parse server-sent events."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            stream=StreamingBody(
                [
                    b": keepalive\n\n",
                    b"event: response.output_text.delta\n",
                    b'data: {"delta":"hi"}\n\n',
                    b"data: [DONE]\n\n",
                    b"data: not json\n\n",
                ]
            ),
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncOpenResponsesClient(
        "https://provider.example",
        http_client=http_client,
    )
    try:
        stream = await client.create(model="model-a", input="hello", stream=True)
        events = [event async for event in stream]
    finally:
        await http_client.aclose()

    assert events == [{"delta": "hi", "type": "response.output_text.delta"}]
    assert requests[0].read() == b'{"model":"model-a","input":"hello","stream":true}'


async def test_stream_maps_error_status_after_reading_body() -> None:
    """Test streaming status errors include the response payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            stream=StreamingBody([b'{"error":{"message":"forbidden"}}']),
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncOpenResponsesClient(
        "https://provider.example",
        http_client=http_client,
    )
    try:
        stream = await client.create(model="model-a", input="hello", stream=True)
        with pytest.raises(AuthenticationError) as err:
            _ = [event async for event in stream]
    finally:
        await http_client.aclose()

    assert str(err.value) == "forbidden"
    assert err.value.response_body == {"error": {"message": "forbidden"}}
