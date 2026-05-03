"""Tests for Open Responses entity helpers."""

from collections.abc import AsyncGenerator
from typing import cast

from openai._streaming import AsyncStream
from openai.types.responses import (
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseReasoningItem,
    ResponseStreamEvent,
)
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.open_responses.entity import (
    _convert_content_to_param,
    _format_tool,
    _transform_stream,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm


class EnumTool(llm.Tool):
    """Tool with unsupported schema keywords."""

    name = "enum_tool"
    description = "Test tool"
    parameters = vol.Schema({vol.Required("mode"): vol.In(["auto", "manual"])})

    async def async_call(self, hass: HomeAssistant, tool_input, llm_context):
        """No-op implementation."""
        return {"mode": "auto"}


def test_format_tool_strips_unsupported_schema_keywords() -> None:
    """Test unsupported JSON Schema keywords are removed from tool schemas."""
    tool = _format_tool(EnumTool(), None)

    assert "enum" not in tool["parameters"]["properties"]["mode"]


def test_convert_content_preserves_system_role() -> None:
    """Test system content remains a system message."""
    messages = _convert_content_to_param(
        [conversation.SystemContent(content="Follow these rules")]
    )

    assert messages == [
        {
            "type": "message",
            "role": "system",
            "content": "Follow these rules",
        }
    ]


def test_convert_content_adds_function_call_status() -> None:
    """Test assistant function call history includes the completed status."""
    messages = _convert_content_to_param(
        [
            conversation.AssistantContent(
                agent_id="agent",
                tool_calls=[
                    llm.ToolInput(
                        id="call_1",
                        tool_name="HassTurnOn",
                        tool_args={"name": "Kitchen"},
                    )
                ],
            )
        ]
    )

    assert messages == [
        {
            "type": "function_call",
            "name": "HassTurnOn",
            "arguments": '{"name":"Kitchen"}',
            "call_id": "call_1",
            "status": "completed",
        }
    ]


def test_convert_content_preserves_native_output_message() -> None:
    """Test native Open Responses output messages are passed back unchanged."""
    native_message = ResponseOutputMessage(
        id="msg_1",
        content=[],
        role="assistant",
        status="completed",
        type="message",
        phase="answer",
    )

    messages = _convert_content_to_param(
        [
            conversation.AssistantContent(
                agent_id="agent",
                content="Done",
                native=native_message,
            )
        ]
    )

    assert messages == [
        {
            "id": "msg_1",
            "content": [],
            "role": "assistant",
            "status": "completed",
            "type": "message",
            "phase": "answer",
        }
    ]


def test_convert_content_preserves_native_dict_output_message() -> None:
    """Test native dict output messages with phase labels are preserved."""
    native_message = {
        "id": "msg_1",
        "content": [
            {
                "type": "output_text",
                "text": "Done",
            }
        ],
        "role": "assistant",
        "status": "completed",
        "type": "message",
        "phase": "answer",
    }

    messages = _convert_content_to_param(
        [
            conversation.AssistantContent(
                agent_id="agent",
                content="Done",
                native=native_message,
            )
        ]
    )

    assert messages == [native_message]


async def test_transform_stream_preserves_native_output_message() -> None:
    """Test output item metadata is preserved from the stream."""
    native_message = ResponseOutputMessage(
        id="msg_1",
        content=[],
        role="assistant",
        status="completed",
        type="message",
        phase="answer",
    )

    async def stream() -> AsyncGenerator[ResponseStreamEvent]:
        yield ResponseOutputItemDoneEvent(
            item=native_message,
            output_index=0,
            sequence_number=0,
            type="response.output_item.done",
        )

    deltas = [
        delta
        async for delta in _transform_stream(
            cast(conversation.ChatLog, object()),
            cast(AsyncStream[ResponseStreamEvent], stream()),
        )
    ]

    assert deltas == [{"native": native_message}]


async def test_transform_stream_starts_new_message_for_reasoning_item() -> None:
    """Test each reasoning item starts a separate assistant message."""
    first_reasoning = ResponseReasoningItem(
        id="reasoning_1",
        summary=[],
        type="reasoning",
    )
    second_reasoning = ResponseReasoningItem(
        id="reasoning_2",
        summary=[],
        type="reasoning",
    )

    async def stream() -> AsyncGenerator[ResponseStreamEvent]:
        yield ResponseOutputItemAddedEvent(
            item=first_reasoning,
            output_index=0,
            sequence_number=0,
            type="response.output_item.added",
        )
        yield ResponseOutputItemDoneEvent(
            item=first_reasoning,
            output_index=0,
            sequence_number=0,
            type="response.output_item.done",
        )
        yield ResponseOutputItemAddedEvent(
            item=second_reasoning,
            output_index=1,
            sequence_number=0,
            type="response.output_item.added",
        )
        yield ResponseOutputItemDoneEvent(
            item=second_reasoning,
            output_index=1,
            sequence_number=0,
            type="response.output_item.done",
        )

    deltas = [
        delta
        async for delta in _transform_stream(
            cast(conversation.ChatLog, object()),
            cast(AsyncStream[ResponseStreamEvent], stream()),
        )
    ]

    assert deltas == [
        {"role": "assistant"},
        {"native": first_reasoning},
        {"role": "assistant"},
        {"native": second_reasoning},
    ]
