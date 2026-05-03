"""Tests for Open Responses entity helpers."""

from collections.abc import AsyncGenerator
from typing import cast

from openai._streaming import AsyncStream
from openai.types.responses import (
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseFunctionToolCall,
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


def test_convert_content_includes_attachment_only_user_message(
    hass: HomeAssistant,
) -> None:
    """Test attachment-only user content remains addressable for file assembly."""
    messages = _convert_content_to_param(
        [
            conversation.UserContent(
                content="",
                attachments=[
                    conversation.Attachment(
                        media_content_id="media-source://media/door.jpg",
                        mime_type="image/jpeg",
                        path=hass.config.path("door.jpg"),
                    )
                ],
            )
        ]
    )

    assert messages == [{"type": "message", "role": "user", "content": ""}]


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


async def test_transform_stream_correlates_tool_deltas_by_item_id() -> None:
    """Test interleaved function call deltas are correlated by item ID."""

    async def stream() -> AsyncGenerator[ResponseStreamEvent]:
        yield ResponseOutputItemAddedEvent(
            item=ResponseFunctionToolCall(
                id="fc_1",
                arguments="",
                call_id="call_1",
                name="FirstTool",
                type="function_call",
                status="in_progress",
            ),
            output_index=0,
            sequence_number=0,
            type="response.output_item.added",
        )
        yield ResponseOutputItemAddedEvent(
            item=ResponseFunctionToolCall(
                id="fc_2",
                arguments="",
                call_id="call_2",
                name="SecondTool",
                type="function_call",
                status="in_progress",
            ),
            output_index=1,
            sequence_number=1,
            type="response.output_item.added",
        )
        yield ResponseFunctionCallArgumentsDeltaEvent(
            delta='{"value"',
            item_id="fc_1",
            output_index=0,
            sequence_number=2,
            type="response.function_call_arguments.delta",
        )
        yield ResponseFunctionCallArgumentsDeltaEvent(
            delta='{"name"',
            item_id="fc_2",
            output_index=1,
            sequence_number=3,
            type="response.function_call_arguments.delta",
        )
        yield ResponseFunctionCallArgumentsDeltaEvent(
            delta=":1}",
            item_id="fc_1",
            output_index=0,
            sequence_number=4,
            type="response.function_call_arguments.delta",
        )
        yield ResponseFunctionCallArgumentsDeltaEvent(
            delta=':"kitchen"}',
            item_id="fc_2",
            output_index=1,
            sequence_number=5,
            type="response.function_call_arguments.delta",
        )
        yield ResponseFunctionCallArgumentsDoneEvent(
            arguments='{"name":"kitchen"}',
            item_id="fc_2",
            name="SecondTool",
            output_index=1,
            sequence_number=6,
            type="response.function_call_arguments.done",
        )
        yield ResponseFunctionCallArgumentsDoneEvent(
            arguments='{"value":1}',
            item_id="fc_1",
            name="FirstTool",
            output_index=0,
            sequence_number=7,
            type="response.function_call_arguments.done",
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
        {"role": "assistant"},
        {
            "tool_calls": [
                llm.ToolInput(
                    id="call_2",
                    tool_name="SecondTool",
                    tool_args={"name": "kitchen"},
                )
            ]
        },
        {
            "tool_calls": [
                llm.ToolInput(
                    id="call_1",
                    tool_name="FirstTool",
                    tool_args={"value": 1},
                )
            ]
        },
    ]


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
