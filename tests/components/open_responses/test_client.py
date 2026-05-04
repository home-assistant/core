"""Tests for the Open Responses client."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import httpx
from pydantic import ValidationError
import pytest

from homeassistant.components.open_responses.client import (
    OpenResponsesClient,
    OpenResponsesInvalidModelError,
    _format_request_body,
    _iter_sse_events,
    _raise_client_error,
)


def test_format_request_body_preserves_tool_parameters() -> None:
    """Test request validation does not strip function tool schemas."""
    body = _format_request_body(
        {
            "model": "model",
            "input": [{"type": "message", "role": "user", "content": "hi"}],
            "stream": True,
            "tools": [
                {
                    "type": "function",
                    "name": "HassGetState",
                    "description": "Get a state",
                    "parameters": {
                        "type": "object",
                        "properties": {"entity_id": {"type": "string"}},
                        "required": ["entity_id"],
                    },
                    "strict": False,
                }
            ],
        }
    )

    assert body["tools"][0]["parameters"] == {
        "type": "object",
        "properties": {"entity_id": {"type": "string"}},
        "required": ["entity_id"],
    }


def test_format_request_body_validates_response_body() -> None:
    """Test request bodies are validated against Open Responses types."""
    with pytest.raises(ValidationError):
        _format_request_body(
            {
                "model": "model",
                "input": "ping",
                "max_output_tokens": 1,
                "stream": False,
            }
        )


async def test_create_response_requests_json() -> None:
    """Test non-streaming responses request a JSON response."""
    response = httpx.Response(
        200,
        json={"id": "resp_1"},
        request=httpx.Request("POST", "https://example.local/v1/responses"),
    )
    http_client = AsyncMock()
    http_client.post.return_value = response
    client = OpenResponsesClient(http_client, "api-key", "https://example.local/v1")

    assert await client.create_response(
        model="model",
        input=[{"type": "message", "role": "user", "content": "ping"}],
    ) == {"id": "resp_1"}

    assert http_client.post.await_args.kwargs["headers"]["accept"] == "application/json"


async def test_stream_response_requests_event_stream() -> None:
    """Test streaming responses request server-sent events."""
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            content=b'data: {"type": "response.created"}\n\ndata: [DONE]\n\n',
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenResponsesClient(http_client, "api-key", "https://example.local/v1")

        assert [
            event
            async for event in client.stream_response(
                model="model",
                input=[{"type": "message", "role": "user", "content": "ping"}],
            )
        ] == [{"type": "response.created"}]

    assert requests[0].headers["accept"] == "text/event-stream"


async def test_iter_sse_events_accumulates_multiline_data() -> None:
    """Test SSE data lines are joined until the event delimiter."""

    async def lines() -> AsyncGenerator[str]:
        yield "event: response.output_text.delta"
        yield 'data: {"delta":'
        yield 'data: "hello"}'
        yield ""

    assert [event async for event in _iter_sse_events(lines())] == [
        {
            "delta": "hello",
            "type": "response.output_text.delta",
        }
    ]


async def test_iter_sse_events_stops_on_done() -> None:
    """Test the OpenAI stream terminator stops event iteration."""

    async def lines() -> AsyncGenerator[str]:
        yield 'data: {"type": "response.created"}'
        yield ""
        yield "data: [DONE]"
        yield ""
        yield 'data: {"type": "response.output_text.delta", "delta": "late"}'
        yield ""

    assert [event async for event in _iter_sse_events(lines())] == [
        {"type": "response.created"}
    ]


def test_raise_client_error_detects_invalid_model() -> None:
    """Test model validation errors are separated from endpoint failures."""
    response = httpx.Response(
        400,
        json={"error": {"message": "Unknown model", "param": "model"}},
        request=httpx.Request("POST", "https://example.local/v1/responses"),
    )

    with pytest.raises(OpenResponsesInvalidModelError):
        _raise_client_error(
            httpx.HTTPStatusError(
                "bad request", request=response.request, response=response
            )
        )
