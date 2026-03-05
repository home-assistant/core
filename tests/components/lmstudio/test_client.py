"""Tests for the LM Studio client."""

from __future__ import annotations

from collections.abc import AsyncIterator

import aiohttp
import pytest

from homeassistant.components.lmstudio.client import (
    LMStudioAuthError,
    LMStudioClient,
    LMStudioConnectionError,
    LMStudioResponseError,
    LMStudioStreamEvent,
    _iter_sse,
)
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker


async def _iter_bytes(lines: list[bytes]) -> AsyncIterator[bytes]:
    """Yield a sequence of byte lines."""
    for line in lines:
        yield line


class _FakeResponse:
    """Minimal response object with async content iteration."""

    def __init__(self, lines: list[bytes]) -> None:
        """Store response lines."""
        self.content = _iter_bytes(lines)


async def test_list_models_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test listing models filters invalid entries."""
    client = LMStudioClient(
        hass=hass,
        base_url="http://localhost:1234",
        api_key="test-key",
        timeout=5,
    )

    aioclient_mock.get(
        "http://localhost:1234/api/v1/models",
        json={"models": [{"key": "model-1"}, "bad", {"key": "model-2"}]},
    )

    models = await client.async_list_models()

    assert models == [{"key": "model-1"}, {"key": "model-2"}]


async def test_list_models_invalid_payload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test listing models handles invalid payloads."""
    client = LMStudioClient(
        hass=hass,
        base_url="http://localhost:1234",
        api_key=None,
        timeout=5,
    )

    aioclient_mock.get(
        "http://localhost:1234/api/v1/models",
        json={"models": "bad"},
    )

    with pytest.raises(LMStudioResponseError):
        await client.async_list_models()


async def test_list_models_auth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test listing models raises auth errors."""
    client = LMStudioClient(
        hass=hass,
        base_url="http://localhost:1234",
        api_key=None,
        timeout=5,
    )

    aioclient_mock.get("http://localhost:1234/api/v1/models", status=401)

    with pytest.raises(LMStudioAuthError):
        await client.async_list_models()


async def test_list_models_response_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test listing models raises response errors."""
    client = LMStudioClient(
        hass=hass,
        base_url="http://localhost:1234",
        api_key=None,
        timeout=5,
    )

    aioclient_mock.get("http://localhost:1234/api/v1/models", status=500, text="boom")

    with pytest.raises(LMStudioResponseError):
        await client.async_list_models()


async def test_list_models_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test listing models handles connection errors."""
    client = LMStudioClient(
        hass=hass,
        base_url="http://localhost:1234",
        api_key=None,
        timeout=5,
    )

    aioclient_mock.get(
        "http://localhost:1234/api/v1/models",
        exc=aiohttp.ClientError("offline"),
    )

    with pytest.raises(LMStudioConnectionError):
        await client.async_list_models()


async def test_stream_chat_http_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test streaming chat returns response errors."""
    client = LMStudioClient(
        hass=hass,
        base_url="http://localhost:1234",
        api_key=None,
        timeout=5,
    )

    aioclient_mock.post(
        "http://localhost:1234/api/v1/chat",
        status=400,
        text="bad",
    )

    with pytest.raises(LMStudioResponseError):
        async for _ in client.async_stream_chat({"model": "test-model"}):
            pass


async def test_iter_sse_parses_events() -> None:
    """Test parsing SSE events."""
    lines = [
        b": comment\n",
        b"event: message.delta\n",
        b'data: {"content": "Hello"}\n',
        b"\n",
        b'data: {"type": "chat.end", "response_id": "resp-1"}\n',
        b"\n",
    ]

    response = _FakeResponse(lines)

    events = [event async for event in _iter_sse(response)]

    assert events == [
        LMStudioStreamEvent("message.delta", {"content": "Hello"}),
        LMStudioStreamEvent("chat.end", {"type": "chat.end", "response_id": "resp-1"}),
    ]


async def test_iter_sse_skips_invalid_payload() -> None:
    """Test parsing skips invalid JSON payloads."""
    lines = [
        b"data: {bad json\n",
        b"\n",
        b'data: {"type": "message.delta", "content": "ok"}\n',
        b"\n",
    ]

    response = _FakeResponse(lines)

    events = [event async for event in _iter_sse(response)]

    assert events == [
        LMStudioStreamEvent("message.delta", {"type": "message.delta", "content": "ok"})
    ]


async def test_stream_chat_auth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test streaming chat raises auth error on 401."""
    client = LMStudioClient(
        hass=hass,
        base_url="http://localhost:1234",
        api_key=None,
        timeout=5,
    )

    aioclient_mock.post("http://localhost:1234/api/v1/chat", status=401)

    with pytest.raises(LMStudioAuthError):
        async for _ in client.async_stream_chat({"model": "test-model"}):
            pass


async def test_stream_chat_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test streaming chat raises connection error on network failure."""
    client = LMStudioClient(
        hass=hass,
        base_url="http://localhost:1234",
        api_key=None,
        timeout=5,
    )

    aioclient_mock.post(
        "http://localhost:1234/api/v1/chat",
        exc=aiohttp.ClientError("offline"),
    )

    with pytest.raises(LMStudioConnectionError):
        async for _ in client.async_stream_chat({"model": "test-model"}):
            pass


async def test_iter_sse_skips_flush_with_no_data() -> None:
    """Test that a flush (empty line) after an event name but no data is skipped."""
    lines = [
        b"event: message.start\n",
        b"\n",
        b'data: {"type": "chat.end"}\n',
        b"\n",
    ]

    response = _FakeResponse(lines)
    events = [event async for event in _iter_sse(response)]

    assert len(events) == 1
    assert events[0].name == "chat.end"


async def test_iter_sse_skips_event_without_type() -> None:
    """Test that a data payload with no event name and no type field is skipped."""
    lines = [
        b'data: {"no_type_field": true}\n',
        b"\n",
        b'data: {"type": "chat.end"}\n',
        b"\n",
    ]

    response = _FakeResponse(lines)
    events = [event async for event in _iter_sse(response)]

    assert len(events) == 1
    assert events[0].name == "chat.end"


async def test_iter_sse_yields_trailing_data() -> None:
    """Test that data at end of stream without a final empty line is still yielded."""
    lines = [
        b'data: {"type": "chat.end", "response_id": "resp-1"}\n',
    ]

    response = _FakeResponse(lines)
    events = [event async for event in _iter_sse(response)]

    assert len(events) == 1
    assert events[0].name == "chat.end"


async def test_iter_sse_skips_trailing_invalid_json() -> None:
    """Test that trailing data with invalid JSON at end of stream is skipped."""
    lines = [
        b"data: {bad json at eof\n",
    ]

    response = _FakeResponse(lines)
    events = [event async for event in _iter_sse(response)]

    assert events == []
