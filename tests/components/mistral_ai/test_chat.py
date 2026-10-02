"""Tests for the chat conversation helpers."""

import json

from mistralai.client.models import (
    CompletionChunk,
    CompletionEvent,
    CompletionResponseStreamChoice,
    DeltaMessage,
    FunctionCall,
    TextChunk,
    ToolCall,
)
from mistralai.client.types import UNSET

from homeassistant.components import conversation
from homeassistant.components.mistral_ai.chat import (
    _extract_text,
    convert_content_to_messages,
    transform_stream,
)
from homeassistant.helpers import llm


def test_extract_text_str() -> None:
    """Plain string content."""
    assert _extract_text("hello") == "hello"


def test_extract_text_unset() -> None:
    """UNSET content returns empty."""
    assert _extract_text(UNSET) == ""


def test_extract_text_none() -> None:
    """None content returns empty."""
    assert _extract_text(None) == ""


def test_extract_text_chunks() -> None:
    """List of content chunks."""
    chunks = [TextChunk(text="Hello"), TextChunk(text=" world")]
    assert _extract_text(chunks) == "Hello world"


def test_extract_text_chunk_dicts() -> None:
    """List of dict chunks."""
    chunks = [{"type": "text", "text": "Hello"}, {"type": "text", "text": " world"}]
    assert _extract_text(chunks) == "Hello world"


def test_convert_system_and_user() -> None:
    """System and user messages."""
    content = [
        conversation.SystemContent(content="You are a home assistant"),
        conversation.UserContent(content="Turn on the light"),
    ]
    messages = convert_content_to_messages(content)
    assert [m.role for m in messages] == ["system", "user"]
    assert messages[0].content == "You are a home assistant"
    assert messages[1].content == "Turn on the light"


def test_convert_assistant_with_tool_calls() -> None:
    """Assistant message with tool calls."""
    tool_input = llm.ToolInput(
        id="tc1", tool_name="HassTurnOn", tool_args={"name": "light"}
    )
    content = [conversation.AssistantContent(agent_id="a", tool_calls=[tool_input])]
    messages = convert_content_to_messages(content)
    assert messages[0].role == "assistant"
    assert messages[0].tool_calls[0].function.name == "HassTurnOn"
    assert json.loads(messages[0].tool_calls[0].function.arguments) == {"name": "light"}


def test_convert_tool_result() -> None:
    """Tool result message."""
    content = [
        conversation.ToolResultContent(
            agent_id="a",
            tool_call_id="tc1",
            tool_name="HassTurnOn",
            result=llm.ToolResult(data={"success": True}),
        )
    ]
    messages = convert_content_to_messages(content)
    assert messages[0].role == "tool"
    assert messages[0].tool_call_id == "tc1"
    assert json.loads(messages[0].content) == {"success": True}


def _event(role=None, content=None, tool_calls=None, finish=None):
    delta = DeltaMessage(
        role=role if role is not None else UNSET,
        content=content if content is not None else UNSET,
        tool_calls=tool_calls if tool_calls is not None else UNSET,
    )
    choice = CompletionResponseStreamChoice(index=0, delta=delta, finish_reason=finish)
    return CompletionEvent(data=CompletionChunk(id="1", model="m", choices=[choice]))


class _Stream:
    def __init__(self, events) -> None:
        self._events = events

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._events:
            raise StopAsyncIteration
        return self._events.pop(0)


async def _collect(stream):
    return [d async for d in transform_stream(stream)]


async def test_transform_stream_text() -> None:
    """Text deltas are yielded with a leading assistant role."""
    events = [
        _event(role="assistant", content="Hello"),
        _event(content=" world"),
    ]
    result = await _collect(_Stream(events))
    assert result == [
        {"role": "assistant"},
        {"content": "Hello"},
        {"content": " world"},
    ]


async def test_transform_stream_tool_calls() -> None:
    """Fragmented tool calls are aggregated by index."""
    events = [
        _event(
            role="assistant",
            tool_calls=[
                ToolCall(
                    id="tc1",
                    index=0,
                    function=FunctionCall(
                        name="HassTurnOn", arguments='{"name":"light'
                    ),
                )
            ],
        ),
        _event(
            tool_calls=[
                ToolCall(index=0, function=FunctionCall(name="", arguments='" }'))
            ]
        ),
        _event(finish="tool_calls"),
    ]
    result = await _collect(_Stream(events))
    tool_calls_result = [d for d in result if "tool_calls" in d]
    assert len(tool_calls_result) == 1
    tool_input = tool_calls_result[0]["tool_calls"][0]
    assert tool_input.tool_name == "HassTurnOn"
    assert tool_input.tool_args == {"name": "light"}
    assert tool_input.id == "tc1"
