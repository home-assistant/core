"""Tests for LM Studio entity helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

import pytest
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.lmstudio import (
    LMStudioConversationStore,
    LMStudioRuntimeData,
)
from homeassistant.components.lmstudio.ai_task import LMStudioTaskEntity
from homeassistant.components.lmstudio.client import (
    LMStudioAuthError,
    LMStudioResponseError,
    LMStudioStreamEvent,
)
from homeassistant.components.lmstudio.const import (
    CONF_CONTEXT_LENGTH,
    CONF_MAX_OUTPUT_TOKENS,
    CONF_MIN_P,
    CONF_REASONING,
    CONF_REPEAT_PENALTY,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
)
from homeassistant.components.lmstudio.entity import LMStudioBaseLLMEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


def _get_subentry(entry: MockConfigEntry, subentry_type: str):
    """Return a subentry by type."""
    return next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == subentry_type
    )


def _make_task_entity(
    hass: HomeAssistant, entry: MockConfigEntry
) -> LMStudioTaskEntity:
    """Create a task entity for tests."""
    subentry = _get_subentry(entry, "ai_task_data")
    entity = LMStudioTaskEntity(entry, subentry)
    entity.hass = hass
    return entity


def test_add_optional_params(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test optional parameters are added and normalized."""
    entity = _make_task_entity(hass, mock_config_entry)

    payload: dict[str, object] = {}
    settings = {
        CONF_MAX_OUTPUT_TOKENS: 128,
        CONF_TEMPERATURE: 0.5,
        CONF_TOP_P: 0.9,
        CONF_TOP_K: 40,
        CONF_MIN_P: 0.05,
        CONF_REPEAT_PENALTY: 1.1,
        CONF_CONTEXT_LENGTH: 4096,
        CONF_REASONING: "medium",
    }

    entity._add_optional_params(payload, settings)

    assert payload["max_output_tokens"] == 128
    assert payload["temperature"] == 0.5
    assert payload["top_p"] == 0.9
    assert payload["top_k"] == 40
    assert payload["min_p"] == 0.05
    assert payload["repeat_penalty"] == 1.1
    assert payload["context_length"] == 4096
    assert payload["reasoning"] == "medium"


def test_reasoning_off_skips_parameter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reasoning parameter is skipped when set to off."""
    entity = _make_task_entity(hass, mock_config_entry)

    payload: dict[str, object] = {}
    entity._add_optional_params(payload, {CONF_REASONING: "off"})

    assert "reasoning" not in payload


async def test_encode_attachments(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test encoding image attachments."""
    entity = _make_task_entity(hass, mock_config_entry)
    file_path = tmp_path / "image.png"
    file_path.write_bytes(b"fake-image")

    attachment = conversation.Attachment(
        media_content_id="media-id",
        mime_type="image/png",
        path=file_path,
    )

    encoded = await entity._async_encode_attachments([attachment])

    assert encoded[0]["type"] == "image"
    assert encoded[0]["data_url"].startswith("data:image/png;base64,")


async def test_encode_attachments_rejects_non_image(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test non-image attachments raise errors."""
    entity = _make_task_entity(hass, mock_config_entry)

    attachment = conversation.Attachment(
        media_content_id="media-id",
        mime_type="text/plain",
        path=Path("note.txt"),
    )

    with pytest.raises(HomeAssistantError) as err:
        await entity._async_encode_attachments([attachment])

    assert err.value.translation_key == "unsupported_attachment_type"


async def test_encode_image_missing_file(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test missing attachment files raise errors."""
    entity = _make_task_entity(hass, mock_config_entry)
    missing_path = tmp_path / "missing.png"

    with pytest.raises(HomeAssistantError) as err:
        await entity._async_encode_image(str(missing_path), "image/png")

    assert err.value.translation_key == "attachment_not_found"


def test_add_structure_prompt_without_system_prompt() -> None:
    """Test structure prompt is generated without a system prompt."""
    schema = vol.Schema({vol.Required("answer"): str})

    result = LMStudioBaseLLMEntity._add_structure_prompt("", schema, None)

    assert result.startswith("Return only valid JSON")


@dataclass
class _DummyChatLog:
    """Minimal chat log stub for stream tests."""

    conversation_id: str
    traces: list[dict[str, object]]

    def async_trace(self, data: dict[str, object]) -> None:
        """Store trace information."""
        self.traces.append(data)


class _DummyClient:
    """Client stub for streaming tests."""

    def __init__(self, events: list[LMStudioStreamEvent]) -> None:
        """Store events."""
        self._events = events

    async def async_stream_chat(
        self, payload: dict[str, object]
    ) -> AsyncGenerator[LMStudioStreamEvent]:
        """Yield predefined events."""
        for event in self._events:
            yield event


async def test_stream_response_records_metadata(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test streaming response records reasoning and response identifier."""
    events = [
        LMStudioStreamEvent("message.start", {}),
        LMStudioStreamEvent("message.delta", {"content": "Hello"}),
        LMStudioStreamEvent("reasoning.delta", {"content": "Thinking"}),
        LMStudioStreamEvent("message.end", {}),
        LMStudioStreamEvent(
            "chat.end",
            {"response_id": "resp-1", "stats": {"input_tokens": 1}},
        ),
    ]

    entry = mock_config_entry
    entry.runtime_data = LMStudioRuntimeData(
        client=_DummyClient(events),
        conversation_store=LMStudioConversationStore(),
        unavailable_logged=False,
    )

    entity = _make_task_entity(hass, entry)
    chat_log = _DummyChatLog(conversation_id="conv-1", traces=[])

    deltas = [
        delta
        async for delta in entity._async_stream_response(
            chat_log, {"model": "test-model"}, "sig"
        )
    ]

    assert deltas == [
        {"content": "Hello", "role": "assistant"},
        {"thinking_content": "Thinking"},
    ]
    assert chat_log.traces == [{"stats": {"input_tokens": 1}}]
    assert (
        entry.runtime_data.conversation_store.get_previous_response_id(
            "conv-1", entity._model, "sig"
        )
        == "resp-1"
    )


async def test_stream_response_error_event_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test error events raise a Home Assistant error."""
    events = [LMStudioStreamEvent("error", {"message": "bad"})]

    entry = mock_config_entry
    entry.runtime_data = LMStudioRuntimeData(
        client=_DummyClient(events),
        conversation_store=LMStudioConversationStore(),
        unavailable_logged=False,
    )

    entity = _make_task_entity(hass, entry)
    chat_log = _DummyChatLog(conversation_id="conv-2", traces=[])

    with pytest.raises(HomeAssistantError):
        async for _ in entity._async_stream_response(
            chat_log, {"model": "test-model"}, "sig"
        ):
            pass


async def test_stream_response_non_string_delta_skipped(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test message.delta events with non-string content are skipped."""
    events = [
        LMStudioStreamEvent("message.start", {}),
        LMStudioStreamEvent("message.delta", {"content": 42}),  # non-string — skipped
        LMStudioStreamEvent("message.delta", {"content": "hello"}),
        LMStudioStreamEvent("chat.end", {}),
    ]

    entry = mock_config_entry
    entry.runtime_data = LMStudioRuntimeData(
        client=_DummyClient(events),
        conversation_store=LMStudioConversationStore(),
        unavailable_logged=False,
    )

    entity = _make_task_entity(hass, entry)
    chat_log = _DummyChatLog(conversation_id="conv-3", traces=[])

    deltas = [
        delta
        async for delta in entity._async_stream_response(
            chat_log, {"model": "test-model"}, "sig"
        )
    ]

    # Only the valid string delta should be yielded (with role since new_message=True)
    assert len(deltas) == 1
    assert deltas[0]["content"] == "hello"
    assert deltas[0]["role"] == "assistant"


def test_get_system_prompt_empty_content() -> None:
    """Test _get_system_prompt returns empty string when content list is empty."""

    @dataclass
    class _EmptyChatLog:
        content: list = None

        def __post_init__(self):
            self.content = []

    result = LMStudioBaseLLMEntity._get_system_prompt(_EmptyChatLog())
    assert result == ""


def test_get_system_prompt_non_system_first_content() -> None:
    """Test _get_system_prompt returns empty string when first item is not SystemContent."""

    @dataclass
    class _ChatLog:
        content: list

    user_msg = conversation.UserContent(content="hello")
    result = LMStudioBaseLLMEntity._get_system_prompt(_ChatLog(content=[user_msg]))
    assert result == ""


def test_format_history_zero_max_returns_empty(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test _format_history returns empty string when max_history is 0."""
    entity = _make_task_entity(hass, mock_config_entry)

    @dataclass
    class _ChatLog:
        content: list

    result = entity._format_history(_ChatLog(content=[]), max_history=0)
    assert result == ""


def test_format_history_with_tool_result_and_other_roles(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test _format_history formats tool_result and unknown role content."""
    entity = _make_task_entity(hass, mock_config_entry)

    system = conversation.SystemContent(content="sys")
    user = conversation.UserContent(content="question")
    tool_result = conversation.ToolResultContent(
        agent_id="agent",
        tool_call_id="call-1",
        tool_name="my_tool",
        tool_result="result_data",
    )
    # Current user message that gets excluded from history (last item)
    user2 = conversation.UserContent(content="new")

    @dataclass
    class _ChatLog:
        content: list

    log = _ChatLog(content=[system, user, tool_result, user2])
    result = entity._format_history(log, max_history=10)

    assert "question" in result
    assert "my_tool" in result
    assert "result_data" in result


def test_format_history_non_user_content_before_any_user_message(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test _format_history ignores non-user content before any user message."""
    entity = _make_task_entity(hass, mock_config_entry)

    system = conversation.SystemContent(content="sys")
    assistant = conversation.AssistantContent(agent_id="agent1", content="hi")
    user_latest = conversation.UserContent(content="latest")

    @dataclass
    class _ChatLog:
        content: list

    # assistant before any user message in [1:-1] — should be skipped
    log = _ChatLog(content=[system, assistant, user_latest])
    result = entity._format_history(log, max_history=10)

    # The assistant content before a user message has no current_round, so skipped
    assert result == ""


async def test_build_input_payload_with_attachments(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test _async_build_input_payload returns list format when attachments present."""
    entity = _make_task_entity(hass, mock_config_entry)
    file_path = tmp_path / "img.png"
    file_path.write_bytes(b"data")

    attachment = conversation.Attachment(
        media_content_id="m",
        mime_type="image/png",
        path=file_path,
    )

    result = await entity._async_build_input_payload("hello", [attachment])

    assert isinstance(result, list)
    assert result[0] == {"type": "message", "content": "hello"}
    assert result[1]["type"] == "image"
    assert result[1]["data_url"].startswith("data:image/png;base64,")


async def test_encode_attachments_guesses_mime_type(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test _async_encode_attachments guesses MIME type when not provided."""
    entity = _make_task_entity(hass, mock_config_entry)
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(b"jpeg-data")

    attachment = conversation.Attachment(
        media_content_id="m",
        mime_type=None,  # not provided — should be guessed from filename
        path=file_path,
    )

    encoded = await entity._async_encode_attachments([attachment])

    assert encoded[0]["type"] == "image"
    assert "image/jpeg" in encoded[0]["data_url"]


async def test_get_latest_user_content_raises_when_absent(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test _get_latest_user_content raises HomeAssistantError when no user content."""

    @dataclass
    class _ChatLog:
        content: list

    log = _ChatLog(
        content=[conversation.AssistantContent(agent_id="agent1", content="hi")]
    )

    with pytest.raises(HomeAssistantError) as err:
        LMStudioBaseLLMEntity._get_latest_user_content(log)

    assert err.value.translation_key == "no_user_content"


async def test_handle_chat_log_auth_error_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test _async_handle_chat_log translates auth errors."""

    class _AuthErrorClient:
        async def async_stream_chat(self, payload):
            raise LMStudioAuthError("bad auth")
            yield  # pylint: disable=unreachable

    entry = mock_config_entry
    entry.runtime_data = LMStudioRuntimeData(
        client=_AuthErrorClient(),
        conversation_store=LMStudioConversationStore(),
        unavailable_logged=False,
    )

    entity = _make_task_entity(hass, entry)

    system = conversation.SystemContent(content="sys")
    user = conversation.UserContent(content="hi")

    @dataclass
    class _ChatLog:
        content: list
        conversation_id: str = "conv-auth"
        llm_api: object = None

        async def async_add_delta_content_stream(self, entity_id, stream):
            async for delta in stream:
                yield delta

    with pytest.raises(HomeAssistantError) as err:
        await entity._async_handle_chat_log(_ChatLog(content=[system, user]))

    assert err.value.translation_key == "auth_failed"


async def test_handle_chat_log_response_error_raises(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test _async_handle_chat_log translates response errors."""

    class _ResponseErrorClient:
        async def async_stream_chat(self, payload):
            raise LMStudioResponseError("bad response")
            yield  # pylint: disable=unreachable

    entry = mock_config_entry
    entry.runtime_data = LMStudioRuntimeData(
        client=_ResponseErrorClient(),
        conversation_store=LMStudioConversationStore(),
        unavailable_logged=False,
    )

    entity = _make_task_entity(hass, entry)

    system = conversation.SystemContent(content="sys")
    user = conversation.UserContent(content="hi")

    @dataclass
    class _ChatLog:
        content: list
        conversation_id: str = "conv-resp"
        llm_api: object = None

        async def async_add_delta_content_stream(self, entity_id, stream):
            async for delta in stream:
                yield delta

    with pytest.raises(HomeAssistantError) as err:
        await entity._async_handle_chat_log(_ChatLog(content=[system, user]))

    assert err.value.translation_key == "connection_error"
