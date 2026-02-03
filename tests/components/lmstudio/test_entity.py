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
from homeassistant.components.lmstudio.client import LMStudioStreamEvent
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

    assert "attachment file was not found" in str(err.value)


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
