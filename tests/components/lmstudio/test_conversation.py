"""Tests for the LM Studio conversation integration."""

from collections.abc import AsyncGenerator
import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.lmstudio.client import (
    LMStudioConnectionError,
    LMStudioStreamEvent,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent

from tests.common import MockConfigEntry


def _stream_response(response_id: str) -> list[LMStudioStreamEvent]:
    """Return a basic stream response."""
    return [
        LMStudioStreamEvent("message.start", {}),
        LMStudioStreamEvent("message.delta", {"content": "test "}),
        LMStudioStreamEvent("message.delta", {"content": "response"}),
        LMStudioStreamEvent("message.end", {}),
        LMStudioStreamEvent(
            "chat.end",
            {
                "response_id": response_id,
                "stats": {"input_tokens": 1, "output_tokens": 2},
            },
        ),
    ]


async def _stream_chat(
    self, payload: dict[str, Any]
) -> AsyncGenerator[LMStudioStreamEvent]:
    """Mock streaming chat response."""
    for event in _stream_response("resp-1"):
        yield event


@pytest.mark.usefixtures("mock_init_component")
async def test_chat_streaming(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that streaming responses are assembled."""
    with patch(
        "homeassistant.components.lmstudio.client.LMStudioClient.async_stream_chat",
        new=_stream_chat,
    ):
        result = await conversation.async_converse(
            hass,
            "test message",
            None,
            Context(),
            agent_id=mock_config_entry.entry_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "test response"


@pytest.mark.usefixtures("mock_init_component")
async def test_previous_response_id_used(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test previous_response_id is passed for follow-up messages."""
    payloads: list[dict[str, Any]] = []

    async def stream_chat(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[LMStudioStreamEvent]:
        payloads.append(payload)
        response_id = f"resp-{len(payloads)}"
        for event in _stream_response(response_id):
            yield event

    with patch(
        "homeassistant.components.lmstudio.client.LMStudioClient.async_stream_chat",
        new=stream_chat,
    ):
        await conversation.async_converse(
            hass,
            "test message",
            "conversation-id",
            Context(),
            agent_id=mock_config_entry.entry_id,
        )
        await conversation.async_converse(
            hass,
            "test message 2",
            "conversation-id",
            Context(),
            agent_id=mock_config_entry.entry_id,
        )

    assert len(payloads) == 2
    assert payloads[0]["model"] == "test-model"
    assert "previous_response_id" not in payloads[0]
    assert payloads[0]["input"] == "test message"
    assert payloads[1]["previous_response_id"] == "resp-1"
    assert payloads[1]["input"] == "test message 2"
    assert "You are helpful." in payloads[0]["system_prompt"]


@pytest.mark.usefixtures("mock_init_component")
async def test_unavailable_logging_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test logging and availability when the server is unavailable and recovers."""
    caplog.set_level(logging.INFO)

    async def fail_stream(
        self, payload: dict[str, Any]
    ) -> AsyncGenerator[LMStudioStreamEvent]:
        raise LMStudioConnectionError("offline")
        yield  # pylint: disable=unreachable

    with patch(
        "homeassistant.components.lmstudio.client.LMStudioClient.async_stream_chat",
        new=fail_stream,
    ):
        await conversation.async_converse(
            hass,
            "test message",
            "conversation-id",
            Context(),
            agent_id=mock_config_entry.entry_id,
        )

    assert "The server is unavailable" in caplog.text
    state = hass.states.get("conversation.lm_studio_conversation")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    caplog.clear()

    with patch(
        "homeassistant.components.lmstudio.client.LMStudioClient.async_stream_chat",
        new=_stream_chat,
    ):
        await conversation.async_converse(
            hass,
            "test message 2",
            "conversation-id",
            Context(),
            agent_id=mock_config_entry.entry_id,
        )

    assert "The server is back online" in caplog.text
    state = hass.states.get("conversation.lm_studio_conversation")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_init_component")
async def test_converse_error_returns_error_result(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a ConverseError during LLM data provision returns an error result."""
    _response = intent.IntentResponse(language="en")
    _response.async_set_error(intent.IntentResponseErrorCode.UNKNOWN, "error")
    _converse_error = conversation.ConverseError("error", "conv-id", _response)

    with patch(
        "homeassistant.components.conversation.chat_log.ChatLog.async_provide_llm_data",
        AsyncMock(side_effect=_converse_error),
    ):
        result = await conversation.async_converse(
            hass,
            "test message",
            None,
            Context(),
            agent_id=mock_config_entry.entry_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
