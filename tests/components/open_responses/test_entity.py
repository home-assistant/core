"""Tests for Open Responses entity helpers."""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

from openresponses.exceptions import (
    AuthenticationError,
    BadRequestError,
    OpenResponsesError,
    RateLimitError,
)
import pytest
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.open_responses.entity import (
    OpenResponsesEntity,
    _async_prepare_message_attachments,
    _convert_content_to_param,
    _event_to_dict,
    _format_structured_output,
    _format_tool,
    _transform_stream,
    async_prepare_files_for_prompt,
)
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import llm


class EnumTool(llm.Tool):
    """Tool with unsupported schema keywords."""

    name = "enum_tool"
    description = "Test tool"
    parameters = vol.Schema({vol.Required("mode"): vol.In(["auto", "manual"])})

    async def async_call(self, hass: HomeAssistant, tool_input, llm_context):
        """No-op implementation."""
        return {"mode": "auto"}


def _authentication_error() -> AuthenticationError:
    """Return a mock API authentication error."""
    return AuthenticationError(
        message="invalid api key",
        status_code=401,
        response_body={"error": {"type": "authentication_error"}},
    )


def _bad_request_error() -> BadRequestError:
    """Return a mock API bad request error."""
    return BadRequestError(
        message="bad request",
        status_code=400,
        response_body={"error": {"message": "bad request"}},
    )


def _rate_limit_error() -> RateLimitError:
    """Return a mock API rate limit error."""
    return RateLimitError(
        message="rate limited",
        status_code=429,
        response_body=None,
    )


def test_format_tool_strips_unsupported_schema_keywords() -> None:
    """Test unsupported JSON Schema keywords are removed from tool schemas."""
    tool = _format_tool(EnumTool(), None)

    assert "enum" not in tool["parameters"]["properties"]["mode"]


def test_format_structured_output_adjusts_nested_schema() -> None:
    """Test structured output schemas are adjusted for Open Responses."""
    schema = _format_structured_output(
        vol.Schema(
            {
                vol.Required("name"): str,
                vol.Optional("tags"): [str],
                vol.Optional("details"): {vol.Optional("room"): str},
            }
        ),
        None,
    )

    assert schema["strict"] is True
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["name", "tags", "details"]
    assert schema["properties"]["tags"]["type"] == ["array", "null"]
    assert schema["properties"]["tags"]["items"]["type"] == "string"
    assert schema["properties"]["details"]["type"] == ["object", "null"]
    assert schema["properties"]["details"]["required"] == ["room"]
    assert schema["properties"]["details"]["properties"]["room"]["type"] == [
        "string",
        "null",
    ]


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
    native_message = {
        "id": "msg_1",
        "content": [],
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


def test_convert_content_includes_tool_result_output() -> None:
    """Test tool results are included as function call outputs."""
    messages = _convert_content_to_param(
        [
            conversation.ToolResultContent(
                agent_id="agent",
                tool_call_id="call_1",
                tool_name="HassTurnOn",
                tool_result={"state": "on"},
            )
        ]
    )

    assert messages == [
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": '{"state":"on"}',
        }
    ]


async def test_prepare_message_attachments_preserves_earlier_turns(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test attachments on previous user turns remain in the request input."""
    image_path = tmp_path / "door.jpg"
    image_path.write_bytes(b"image")
    chat_content = [
        conversation.UserContent(
            content="",
            attachments=[
                conversation.Attachment(
                    media_content_id="media-source://media/door.jpg",
                    mime_type="image/jpeg",
                    path=image_path,
                )
            ],
        ),
        conversation.AssistantContent(
            agent_id="agent",
            content="I can see it.",
            native={"type": "message", "id": "msg_1"},
        ),
        conversation.UserContent(content="What color is it?"),
    ]
    messages = _convert_content_to_param(chat_content)

    await _async_prepare_message_attachments(hass, chat_content, messages)

    assert messages[0]["content"] == [
        {
            "type": "input_image",
            "image_url": "data:image/jpeg;base64,aW1hZ2U=",
            "detail": "auto",
        }
    ]
    assert messages[2] == {
        "type": "message",
        "role": "user",
        "content": "What color is it?",
    }


async def test_prepare_message_attachments_skips_tool_results(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test attachment insertion indexes past tool result messages."""
    image_path = tmp_path / "door.jpg"
    image_path.write_bytes(b"image")
    chat_content = [
        conversation.ToolResultContent(
            agent_id="agent",
            tool_call_id="call_1",
            tool_name="HassTurnOn",
            tool_result={"state": "on"},
        ),
        conversation.UserContent(
            content="What changed?",
            attachments=[
                conversation.Attachment(
                    media_content_id="media-source://media/door.jpg",
                    mime_type="image/jpeg",
                    path=image_path,
                )
            ],
        ),
    ]
    messages = _convert_content_to_param(chat_content)

    await _async_prepare_message_attachments(hass, chat_content, messages)

    assert messages[0]["type"] == "function_call_output"
    assert messages[1]["content"] == [
        {"type": "input_text", "text": "What changed?"},
        {
            "type": "input_image",
            "image_url": "data:image/jpeg;base64,aW1hZ2U=",
            "detail": "auto",
        },
    ]


async def test_prepare_pdf_file_uses_basename(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test PDF filenames do not expose the local path."""
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    assert await async_prepare_files_for_prompt(
        hass, [(pdf_path, "application/pdf")]
    ) == [
        {
            "type": "input_file",
            "filename": "invoice.pdf",
            "file_data": "data:application/pdf;base64,JVBERi0xLjQ=",
        }
    ]


async def test_prepare_file_guesses_image_mime_type(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test image MIME types can be inferred from filenames."""
    image_path = tmp_path / "door.png"
    image_path.write_bytes(b"image")

    assert await async_prepare_files_for_prompt(hass, [(image_path, None)]) == [
        {
            "type": "input_image",
            "image_url": "data:image/png;base64,aW1hZ2U=",
            "detail": "auto",
        }
    ]


async def test_prepare_file_rejects_missing_file(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test missing files fail before request assembly."""
    with pytest.raises(HomeAssistantError, match="does not exist"):
        await async_prepare_files_for_prompt(hass, [(tmp_path / "missing.jpg", None)])


async def test_prepare_file_rejects_unsupported_mime_type(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test unsupported file MIME types fail before request assembly."""
    text_path = tmp_path / "note.txt"
    text_path.write_text("hello")

    with pytest.raises(HomeAssistantError, match="Only images and PDF are supported"):
        await async_prepare_files_for_prompt(hass, [(text_path, "text/plain")])


async def test_transform_stream_preserves_native_output_message() -> None:
    """Test output item metadata is preserved from the stream."""
    native_message = {
        "id": "msg_1",
        "content": [],
        "role": "assistant",
        "status": "completed",
        "type": "message",
        "phase": "answer",
    }

    async def stream() -> AsyncGenerator[dict]:
        yield {
            "item": native_message,
            "output_index": 0,
            "sequence_number": 0,
            "type": "response.output_item.done",
        }

    deltas = [
        delta
        async for delta in _transform_stream(
            Mock(),
            stream(),
        )
    ]

    assert deltas == [{"native": native_message}]


async def test_transform_stream_handles_sdk_event_objects() -> None:
    """Test SDK stream events are converted before handling."""

    class Event:
        def model_dump(self, **kwargs):
            return {"type": "response.output_text.delta", "delta": "hello"}

    async def stream() -> AsyncGenerator[Event]:
        yield Event()

    deltas = [
        delta
        async for delta in _transform_stream(
            Mock(),
            stream(),
        )
    ]

    assert deltas == [{"content": "hello"}]


async def test_transform_stream_handles_open_responses_event_names() -> None:
    """Test Open Responses semantic stream events produce chat deltas."""

    async def stream() -> AsyncGenerator[dict]:
        yield {"type": "response.reasoning.delta", "delta": "checking"}
        yield {"type": "response.text.delta", "delta": "hello"}

    deltas = [
        delta
        async for delta in _transform_stream(
            Mock(),
            stream(),
        )
    ]

    assert deltas == [
        {"thinking_content": "checking"},
        {"content": "hello"},
    ]


async def test_transform_stream_handles_refusal_delta() -> None:
    """Test streamed refusals produce assistant content."""

    async def stream() -> AsyncGenerator[dict]:
        yield {"type": "response.refusal.delta", "delta": "I cannot help with that."}
        yield {"type": "response.refusal.done", "refusal": "I cannot help with that."}

    deltas = [
        delta
        async for delta in _transform_stream(
            Mock(),
            stream(),
        )
    ]

    assert deltas == [{"content": "I cannot help with that."}]


async def test_transform_stream_correlates_tool_deltas_by_item_id() -> None:
    """Test interleaved function call deltas are correlated by item ID."""

    async def stream() -> AsyncGenerator[dict]:
        yield {
            "item": {
                "id": "fc_1",
                "arguments": "",
                "call_id": "call_1",
                "name": "FirstTool",
                "type": "function_call",
                "status": "in_progress",
            },
            "output_index": 0,
            "sequence_number": 0,
            "type": "response.output_item.added",
        }
        yield {
            "item": {
                "id": "fc_2",
                "arguments": "",
                "call_id": "call_2",
                "name": "SecondTool",
                "type": "function_call",
                "status": "in_progress",
            },
            "output_index": 1,
            "sequence_number": 1,
            "type": "response.output_item.added",
        }
        yield {
            "delta": '{"value"',
            "item_id": "fc_1",
            "output_index": 0,
            "sequence_number": 2,
            "type": "response.function_call_arguments.delta",
        }
        yield {
            "delta": '{"name"',
            "item_id": "fc_2",
            "output_index": 1,
            "sequence_number": 3,
            "type": "response.function_call_arguments.delta",
        }
        yield {
            "delta": ":1}",
            "item_id": "fc_1",
            "output_index": 0,
            "sequence_number": 4,
            "type": "response.function_call_arguments.delta",
        }
        yield {
            "delta": ':"kitchen"}',
            "item_id": "fc_2",
            "output_index": 1,
            "sequence_number": 5,
            "type": "response.function_call_arguments.delta",
        }
        yield {
            "arguments": '{"name":"kitchen"}',
            "item_id": "fc_2",
            "name": "SecondTool",
            "output_index": 1,
            "sequence_number": 6,
            "type": "response.function_call_arguments.done",
        }
        yield {
            "arguments": '{"value":1}',
            "item_id": "fc_1",
            "name": "FirstTool",
            "output_index": 0,
            "sequence_number": 7,
            "type": "response.function_call_arguments.done",
        }

    deltas = [
        delta
        async for delta in _transform_stream(
            Mock(),
            stream(),
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


async def test_transform_stream_rejects_tool_call_without_item_id() -> None:
    """Test tool calls must include an item ID for delta correlation."""

    async def stream() -> AsyncGenerator[dict]:
        yield {
            "item": {
                "arguments": "",
                "call_id": "call_1",
                "name": "HassTurnOn",
                "type": "function_call",
            },
            "type": "response.output_item.added",
        }

    with pytest.raises(HomeAssistantError, match="without an item ID"):
        [
            delta
            async for delta in _transform_stream(
                Mock(),
                stream(),
            )
        ]


async def test_transform_stream_rejects_tool_arguments_without_tool_call() -> None:
    """Test completed tool arguments must reference a known tool call."""

    async def stream() -> AsyncGenerator[dict]:
        yield {
            "arguments": "{}",
            "item_id": "missing",
            "type": "response.function_call_arguments.done",
        }

    with pytest.raises(HomeAssistantError, match="without a tool call"):
        [
            delta
            async for delta in _transform_stream(
                Mock(),
                stream(),
            )
        ]


async def test_transform_stream_starts_new_message_for_reasoning_item() -> None:
    """Test each reasoning item starts a separate assistant message."""
    first_reasoning = {
        "id": "reasoning_1",
        "summary": [{"type": "summary_text", "text": "Checked the state."}],
        "type": "reasoning",
    }
    second_reasoning = {"id": "reasoning_2", "summary": [], "type": "reasoning"}

    async def stream() -> AsyncGenerator[dict]:
        yield {
            "item": first_reasoning,
            "output_index": 0,
            "sequence_number": 0,
            "type": "response.output_item.added",
        }
        yield {
            "item": first_reasoning,
            "output_index": 0,
            "sequence_number": 0,
            "type": "response.output_item.done",
        }
        yield {
            "item": second_reasoning,
            "output_index": 1,
            "sequence_number": 0,
            "type": "response.output_item.added",
        }
        yield {
            "item": second_reasoning,
            "output_index": 1,
            "sequence_number": 0,
            "type": "response.output_item.done",
        }

    deltas = [
        delta
        async for delta in _transform_stream(
            Mock(),
            stream(),
        )
    ]

    assert deltas == [
        {"role": "assistant"},
        {
            "native": {
                "encrypted_content": None,
                "id": "reasoning_1",
                "summary": [{"type": "summary_text", "text": "Checked the state."}],
                "type": "reasoning",
            }
        },
        {"role": "assistant"},
        {
            "native": {
                "encrypted_content": None,
                "id": "reasoning_2",
                "summary": [],
                "type": "reasoning",
            }
        },
    ]


async def test_transform_stream_starts_new_message_for_reasoning_summary_index() -> (
    None
):
    """Test reasoning summary index changes start a new assistant message."""

    async def stream() -> AsyncGenerator[dict]:
        yield {
            "item": {"id": "reasoning_1", "summary": ["first"], "type": "reasoning"},
            "type": "response.output_item.done",
        }
        yield {
            "delta": "first",
            "summary_index": 0,
            "type": "response.reasoning_summary.delta",
        }
        yield {
            "delta": "second",
            "summary_index": 1,
            "type": "response.reasoning_summary_text.delta",
        }

    deltas = [
        delta
        async for delta in _transform_stream(
            Mock(),
            stream(),
        )
    ]

    assert deltas == [
        {
            "native": {
                "encrypted_content": None,
                "id": "reasoning_1",
                "summary": ["first"],
                "type": "reasoning",
            }
        },
        {"thinking_content": "first"},
        {"role": "assistant"},
        {"thinking_content": "second"},
    ]


async def test_transform_stream_traces_usage() -> None:
    """Test completed responses trace token usage."""
    chat_log = Mock()

    async def stream() -> AsyncGenerator[dict]:
        yield {
            "response": {"usage": {"input_tokens": 2, "output_tokens": 3}},
            "type": "response.completed",
        }

    assert [
        delta
        async for delta in _transform_stream(
            chat_log,
            stream(),
        )
    ] == []
    chat_log.async_trace.assert_called_once_with(
        {"stats": {"input_tokens": 2, "output_tokens": 3}}
    )


@pytest.mark.parametrize(
    ("event", "message"),
    [
        (
            {
                "response": {"incomplete_details": {"reason": "max_output_tokens"}},
                "type": "response.incomplete",
            },
            "Open Responses response incomplete: max_output_tokens",
        ),
        (
            {
                "response": {"error": {"message": "tool output rejected"}},
                "type": "response.failed",
            },
            "Open Responses response failed: tool output rejected",
        ),
    ],
)
async def test_transform_stream_rejects_terminal_failure_events(
    event: dict[str, Any], message: str
) -> None:
    """Test terminal failure events raise Home Assistant errors."""

    async def stream() -> AsyncGenerator[dict]:
        yield event

    with pytest.raises(HomeAssistantError, match=message):
        [
            delta
            async for delta in _transform_stream(
                Mock(),
                stream(),
            )
        ]


async def test_transform_stream_handles_spec_error_envelope() -> None:
    """Test streaming error events use the Open Responses error envelope."""

    async def stream() -> AsyncGenerator[dict]:
        yield {
            "error": {
                "code": "invalid_request",
                "message": "Invalid tool result.",
                "param": "input",
                "type": "invalid_request_error",
            },
            "sequence_number": 0,
            "type": "response.error",
        }

    with pytest.raises(
        HomeAssistantError,
        match="Open Responses response error: Invalid tool result.",
    ):
        [
            delta
            async for delta in _transform_stream(
                Mock(),
                stream(),
            )
        ]


async def test_transform_stream_handles_sdk_error_event() -> None:
    """Test SDK streaming error events use the top-level message."""

    async def stream() -> AsyncGenerator[dict]:
        yield {
            "code": "server_error",
            "message": "Stream failed.",
            "sequence_number": 0,
            "type": "error",
        }

    with pytest.raises(
        HomeAssistantError,
        match="Open Responses response error: Stream failed.",
    ):
        [
            delta
            async for delta in _transform_stream(
                Mock(),
                stream(),
            )
        ]


def test_event_to_dict_uses_to_dict() -> None:
    """Test SDK events with to_dict are converted."""

    class Event:
        def to_dict(self) -> dict[str, str]:
            return {"type": "response.completed"}

    assert _event_to_dict(Event()) == {"type": "response.completed"}


def test_event_to_dict_rejects_unknown_event() -> None:
    """Test unknown SDK event types fail loudly."""
    with pytest.raises(
        HomeAssistantError, match="Received unknown Open Responses stream event"
    ):
        _event_to_dict(object())


async def test_handle_chat_log_passes_structured_output_schema(
    hass: HomeAssistant,
) -> None:
    """Test structured output options are sent to the endpoint."""

    async def stream() -> AsyncGenerator[dict]:
        yield {"type": "response.completed"}

    async def add_delta_content_stream(
        entity_id: str,
        delta_stream: AsyncGenerator[conversation.AssistantContentDeltaDict],
    ) -> AsyncGenerator[conversation.AssistantContent]:
        async for _delta in delta_stream:
            pass
        if entity_id == "":
            yield conversation.AssistantContent(agent_id=entity_id, content="")

    client = Mock()
    client.create = AsyncMock(return_value=stream())
    entity = Mock()
    entity.hass = hass
    entity.entity_id = "conversation.open_responses"
    entity.entry = Mock(
        data={CONF_MODEL: "open-responses-model"},
        runtime_data=client,
    )
    entity.subentry = Mock(data={})
    chat_log = Mock(
        content=[],
        conversation_id="conversation-id",
        llm_api=None,
        unresponded_tool_results=False,
    )
    chat_log.async_add_delta_content_stream = add_delta_content_stream

    await OpenResponsesEntity._async_handle_chat_log(
        entity,
        chat_log,
        structure_name="Response Format",
        structure=vol.Schema({vol.Required("answer"): str}),
    )

    client.create.assert_awaited_once()
    assert client.create.await_args.kwargs["text"] == {
        "format": {
            "type": "json_schema",
            "name": "response_format",
            "schema": {
                "additionalProperties": False,
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "strict": True,
                "type": "object",
            },
        }
    }


@pytest.mark.parametrize(
    ("api_error", "expected_error", "message"),
    [
        (
            _authentication_error(),
            ConfigEntryAuthFailed,
            "Authentication failed with Open Responses endpoint",
        ),
        (
            _rate_limit_error(),
            HomeAssistantError,
            "Rate limited by Open Responses endpoint",
        ),
        (
            _bad_request_error(),
            HomeAssistantError,
            "Open Responses endpoint rejected request",
        ),
        (
            OpenResponsesError("boom"),
            HomeAssistantError,
            "Error talking to Open Responses endpoint",
        ),
    ],
)
async def test_handle_chat_log_maps_api_errors(
    hass: HomeAssistant,
    api_error: OpenResponsesError,
    expected_error: type[Exception],
    message: str,
) -> None:
    """Test API errors are mapped to Home Assistant errors."""
    client = Mock()
    client.create = AsyncMock(side_effect=api_error)
    entity = Mock()
    entity.hass = hass
    entity.entity_id = "conversation.open_responses"
    entity.entry = Mock(
        data={CONF_MODEL: "open-responses-model"},
        runtime_data=client,
    )
    entity.subentry = Mock(data={})
    chat_log = Mock(
        content=[],
        conversation_id="conversation-id",
        llm_api=None,
        unresponded_tool_results=False,
    )

    with pytest.raises(expected_error, match=message):
        await OpenResponsesEntity._async_handle_chat_log(entity, chat_log)


async def test_handle_chat_log_starts_reauth_on_auth_error(
    hass: HomeAssistant,
) -> None:
    """Test runtime authentication failures start the reauth flow."""
    client = Mock()
    client.create = AsyncMock(side_effect=_authentication_error())
    entry = Mock(
        data={CONF_MODEL: "open-responses-model"},
        runtime_data=client,
    )
    entity = Mock()
    entity.hass = hass
    entity.entity_id = "conversation.open_responses"
    entity.entry = entry
    entity.subentry = Mock(data={})
    chat_log = Mock(
        content=[],
        conversation_id="conversation-id",
        llm_api=None,
        unresponded_tool_results=False,
    )

    with pytest.raises(
        ConfigEntryAuthFailed,
        match="Authentication failed with Open Responses endpoint",
    ):
        await OpenResponsesEntity._async_handle_chat_log(entity, chat_log)

    entry.async_start_reauth.assert_called_once_with(hass)
