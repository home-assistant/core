"""Test AI Task structured data generation."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice, ChoiceDelta
import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import ai_task, media_source
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from . import setup_integration
from .conftest import get_generator_from_data

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_openai_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.open_router.PLATFORMS",
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

    entity_id = "ai_task.gemini_1_5_pro"

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=get_generator_from_data(
            [
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[
                        ChunkChoice.model_construct(
                            finish_reason="stop",
                            index=0,
                            delta=ChoiceDelta(
                                content="The test data",
                                role="assistant",
                            ),
                        )
                    ],
                    created=1700000000,
                    model="x-ai/grok-3",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                )
            ]
        )
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
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
        return_value=get_generator_from_data(
            [
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[
                        ChunkChoice.model_construct(
                            finish_reason="stop",
                            index=0,
                            delta=ChoiceDelta(
                                content='{"characters": ["Mario", "Luigi"]}',
                                role="assistant",
                            ),
                        )
                    ],
                    created=1700000000,
                    model="x-ai/grok-3",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                )
            ]
        )
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.gemini_1_5_pro",
        instructions="Generate test data",
        structure=probatio.Schema(
            {
                probatio.Required("characters"): selector.selector(
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
                "additionalProperties": False,
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
        return_value=get_generator_from_data(
            [
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[
                        ChunkChoice.model_construct(
                            finish_reason="stop",
                            index=0,
                            delta=ChoiceDelta(
                                content="INVALID JSON RESPONSE",
                                role="assistant",
                            ),
                        )
                    ],
                    created=1700000000,
                    model="x-ai/grok-3",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                )
            ]
        )
    )

    with pytest.raises(
        HomeAssistantError, match="Error with OpenRouter structured response"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_1_5_pro",
            instructions="Generate test data",
            structure=probatio.Schema(
                {
                    probatio.Required("characters"): selector.selector(
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
    """Test AI Task raises HomeAssistantError when API returns empty choices."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=get_generator_from_data(
            [
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[],
                    created=1700000000,
                    model="x-ai/grok-3",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                )
            ]
        )
    )

    with pytest.raises(HomeAssistantError, match="API returned empty response"):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_1_5_pro",
            instructions="Generate test data",
        )


async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task data generation with attachments."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "ai_task.gemini_1_5_pro"

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=get_generator_from_data(
            [
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[
                        ChunkChoice.model_construct(
                            finish_reason="stop",
                            index=0,
                            delta=ChoiceDelta(
                                content="Hi there!",
                                role="assistant",
                            ),
                        )
                    ],
                    created=1700000000,
                    model="x-ai/grok-3",
                    object="chat.completion.chunk",
                    system_fingerprint=None,
                )
            ]
        )
    )

    # Test with attachments
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
            "homeassistant.components.open_router.entity.guess_file_type",
            return_value=("image/jpeg", None),
        ),
        patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
                {"media_content_id": "media-source://media/context.pdf"},
            ],
        )

    assert result.data == "Hi there!"

    # Verify that the create was called with the correct parameters
    # The last call should have the user message with attachments
    call_args = mock_openai_client.chat.completions.create.call_args
    assert call_args is not None

    # Check that the input includes the attachments
    input_messages = call_args[1]["messages"]
    assert len(input_messages) > 0

    # Find the user message with attachments
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
