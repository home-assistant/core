"""Tests for Open Responses conversation."""

from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant

from tests.common import MockConfigEntry


def _mock_response_stream(calls: list[dict[str, Any]], text: str) -> Any:
    """Return a streaming response mock."""

    async def stream_response(**params: Any) -> AsyncGenerator[dict[str, Any]]:
        calls.append(deepcopy(params))
        yield {
            "type": "response.output_item.added",
            "item": {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "content": [],
                "status": "in_progress",
            },
        }
        yield {"type": "response.output_text.delta", "delta": text}
        yield {
            "type": "response.output_item.done",
            "item": {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
                "status": "completed",
            },
        }
        yield {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 1}},
        }

    return stream_response


async def test_conversation_turn(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test a conversation turn reaches the Open Responses client."""
    calls: list[dict[str, Any]] = []
    mock_config_entry.runtime_data.stream_response = _mock_response_stream(
        calls, "Hello from Open Responses"
    )

    result = await conversation.async_converse(
        hass,
        "hello",
        None,
        Context(),
        agent_id=mock_config_entry.entry_id,
    )

    assert result.response.speech["plain"]["speech"] == "Hello from Open Responses"
    assert calls[0]["model"] == "open-responses-model"
    assert calls[0]["input"][-1] == {
        "type": "message",
        "role": "user",
        "content": "hello",
    }
