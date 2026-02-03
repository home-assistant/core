"""Tests for the LM Studio conversation integration."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.lmstudio.client import LMStudioStreamEvent
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
