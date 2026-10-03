"""Tests for the Mistral AI conversation platform."""

from unittest.mock import AsyncMock, patch

from mistralai.client.models import (
    CompletionChunk,
    CompletionEvent,
    CompletionResponseStreamChoice,
    DeltaMessage,
    FunctionCall,
    ToolCall,
)
from mistralai.client.types import UNSET
import probatio
import pytest

from homeassistant.components import conversation
from homeassistant.components.llm import LLMTools
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.llm import ToolResult

from tests.common import MockConfigEntry

ENTITY_ID = "conversation.mistral_conversation"


def _event(role=None, content=None, tool_calls=None, finish=None) -> CompletionEvent:
    """Build a completion event for the mocked stream."""
    delta = DeltaMessage(
        role=role if role is not None else UNSET,
        content=content if content is not None else UNSET,
        tool_calls=tool_calls if tool_calls is not None else UNSET,
    )
    choice = CompletionResponseStreamChoice(index=0, delta=delta, finish_reason=finish)
    return CompletionEvent(data=CompletionChunk(id="1", model="m", choices=[choice]))


class _Stream:
    """Async iterator over pre-built completion events."""

    def __init__(self, events) -> None:
        """Initialize with the events to yield."""
        self._events = list(events)

    def __aiter__(self):
        """Return self as the async iterator."""
        return self

    async def __anext__(self) -> CompletionEvent:
        """Return the next event or stop."""
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)


@pytest.mark.usefixtures("mock_client", "mock_init_component")
async def test_conversation_agent(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The conversation entity is registered as an agent."""
    agent = conversation.agent_manager.async_get_agent(hass, ENTITY_ID)
    assert agent is not None
    assert agent.supported_languages == "*"


@pytest.mark.usefixtures("mock_init_component")
async def test_streamed_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
) -> None:
    """A streamed response flows through handle_chat_log to the result."""
    mock_client.chat.stream_async.return_value = _Stream(
        [
            _event(role="assistant", content="Hello"),
            _event(content=" world", finish="stop"),
        ]
    )

    result = await conversation.async_converse(
        hass, "hi", None, Context(), agent_id=ENTITY_ID
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Hello world"


@pytest.mark.usefixtures(
    "mock_client", "mock_config_entry_with_assist", "mock_init_component"
)
async def test_tool_round_trip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
) -> None:
    """A tool call is executed and its result sent back to the model."""
    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = probatio.Schema({probatio.Optional("param1"): str})
    mock_tool.async_call.return_value = ToolResult(data={"success": True})

    mock_client.chat.stream_async.side_effect = [
        _Stream(
            [
                _event(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            index=0,
                            function=FunctionCall(
                                name="test_tool", arguments='{"param1": "value"}'
                            ),
                        )
                    ],
                ),
                _event(finish="tool_calls"),
            ]
        ),
        _Stream(
            [
                _event(role="assistant", content="Done"),
                _event(content="!", finish="stop"),
            ]
        ),
    ]

    with patch(
        "homeassistant.components.llm.async_get_tools",
        new_callable=AsyncMock,
        return_value=LLMTools(tools=[mock_tool]),
    ):
        result = await conversation.async_converse(
            hass, "call the tool", None, Context(), agent_id=ENTITY_ID
        )
        await hass.async_block_till_done()

    mock_tool.async_call.assert_awaited_once()
    tool_input = mock_tool.async_call.await_args.args[1]
    assert tool_input.tool_name == "test_tool"
    assert tool_input.tool_args == {"param1": "value"}

    assert mock_client.chat.stream_async.await_count == 2
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Done!"


@pytest.mark.usefixtures("mock_init_component")
async def test_stream_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client,
) -> None:
    """An API error is surfaced as an error response."""
    mock_client.chat.stream_async.side_effect = Exception("boom")

    result = await conversation.async_converse(
        hass, "hi", None, Context(), agent_id=ENTITY_ID
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
