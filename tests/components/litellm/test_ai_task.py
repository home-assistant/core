"""Test AI Task structured data generation."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import ai_task, media_source
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "ai_task.gpt_4"


def _completion(content: str) -> ChatCompletion:
    """Build a chat completion with the given content."""
    return ChatCompletion(
        id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    content=content,
                    role="assistant",
                    function_call=None,
                    tool_calls=None,
                ),
            )
        ],
        created=1700000000,
        model="gpt-4",
        object="chat.completion",
        system_fingerprint=None,
        usage=CompletionUsage(completion_tokens=9, prompt_tokens=8, total_tokens=17),
    )


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.litellm.PLATFORMS",
        [Platform.AI_TASK],
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task data generation."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion("The test data")
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=ENTITY_ID,
        instructions="Generate test data",
    )

    assert result.data == "The test data"


async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task structured data generation."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion('{"characters": ["Mario", "Luigi"]}')
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=ENTITY_ID,
        instructions="Generate test data",
        structure=vol.Schema(
            {
                vol.Required("characters"): selector.selector(
                    {
                        "text": {
                            "multiple": True,
                        }
                    }
                )
            },
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}
    assert mock_openai_client.chat.completions.create.call_args_list[0][1][
        "response_format"
    ] == {
        "json_schema": {
            "name": "Test Task",
            "schema": {
                "properties": {
                    "characters": {
                        "items": {"type": "string"},
                        "type": "array",
                    }
                },
                "required": ["characters"],
                "type": "object",
            },
            "strict": True,
        },
        "type": "json_schema",
    }


async def test_generate_invalid_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task with invalid JSON response."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion("INVALID JSON RESPONSE")
    )

    with pytest.raises(
        HomeAssistantError, match="Error with LiteLLM structured response"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=ENTITY_ID,
            instructions="Generate test data",
            structure=vol.Schema(
                {
                    vol.Required("characters"): selector.selector(
                        {
                            "text": {
                                "multiple": True,
                            }
                        }
                    )
                },
            ),
        )


async def test_generate_data_empty_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task raises an error when the API returns empty choices."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[],
            created=1700000000,
            model="gpt-4",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(completion_tokens=0, prompt_tokens=8, total_tokens=8),
        )
    )

    with pytest.raises(HomeAssistantError, match="API returned empty response"):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=ENTITY_ID,
            instructions="Generate test data",
        )


async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task data generation with attachments."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion("Hi there!")
    )

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpeg",
                    path=Path("doorbell_snapshot.jpg"),
                ),
                media_source.PlayMedia(
                    url="http://example.com/context.pdf",
                    mime_type="application/pdf",
                    path=Path("context.pdf"),
                ),
            ],
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "homeassistant.components.litellm.entity.guess_file_type",
            return_value=("image/jpeg", None),
        ),
        patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=ENTITY_ID,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
                {"media_content_id": "media-source://media/context.pdf"},
            ],
        )

    assert result.data == "Hi there!"

    call_args = mock_openai_client.chat.completions.create.call_args
    assert call_args is not None

    input_messages = call_args[1]["messages"]
    assert len(input_messages) > 0

    user_message_with_attachments = input_messages[-2]

    assert user_message_with_attachments is not None
    assert len(user_message_with_attachments["content"]) == 3  # Text + attachments
    assert user_message_with_attachments["content"] == [
        {"type": "text", "text": "Test prompt"},
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64,ZmFrZV9pbWFnZV9kYXRh"},
        },
        {
            "type": "image_url",
            "image_url": {"url": "data:application/pdf;base64,ZmFrZV9pbWFnZV9kYXRh"},
        },
    ]
