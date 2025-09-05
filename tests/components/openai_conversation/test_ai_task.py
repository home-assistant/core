"""Test AI Task platform of OpenAI Conversation integration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol

from homeassistant.components import ai_task, media_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from . import create_image_gen_call_item, create_message_item

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation."""
    entity_id = "ai_task.openai_ai_task"

    # Ensure entity is linked to the subentry
    entity_entry = entity_registry.async_get(entity_id)
    ai_task_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "ai_task_data"
        )
    )
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="The test data", output_index=0)
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        instructions="Generate test data",
    )

    assert result.data == "The test data"


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task structured data generation."""
    # Mock the OpenAI response stream with JSON data
    mock_create_stream.return_value = [
        create_message_item(
            id="msg_A", text='{"characters": ["Mario", "Luigi"]}', output_index=0
        )
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.openai_ai_task",
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


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_invalid_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task with invalid JSON response."""
    # Mock the OpenAI response stream with invalid JSON
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="INVALID JSON RESPONSE", output_index=0)
    ]

    with pytest.raises(
        HomeAssistantError, match="Error with OpenAI structured response"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
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


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation with attachments."""
    entity_id = "ai_task.openai_ai_task"

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hi there!", output_index=0)
    ]

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
                    url="http://example.com/context.txt",
                    mime_type="text/plain",
                    path=Path("context.txt"),
                ),
            ],
        ),
        patch("pathlib.Path.exists", return_value=True),
        # patch.object(hass.config, "is_allowed_path", return_value=True),
        patch(
            "homeassistant.components.openai_conversation.entity.guess_file_type",
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
                {"media_content_id": "media-source://media/context.txt"},
            ],
        )

    assert result.data == "Hi there!"

    # Verify that the create stream was called with the correct parameters
    # The last call should have the user message with attachments
    call_args = mock_create_stream.call_args
    assert call_args is not None

    # Check that the input includes the attachments
    input_messages = call_args[1]["input"]
    assert len(input_messages) > 0

    # Find the user message with attachments
    user_message_with_attachments = input_messages[-2]

    assert user_message_with_attachments is not None
    assert isinstance(user_message_with_attachments["content"], list)
    assert len(user_message_with_attachments["content"]) == 3  # Text + attachments
    assert user_message_with_attachments["content"] == [
        {"type": "input_text", "text": "Test prompt"},
        {
            "detail": "auto",
            "image_url": "data:image/jpeg;base64,ZmFrZV9pbWFnZV9kYXRh",
            "type": "input_image",
        },
        {
            "detail": "auto",
            "image_url": "data:image/jpeg;base64,ZmFrZV9pbWFnZV9kYXRh",
            "type": "input_image",
        },
    ]


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task image generation."""
    entity_id = "ai_task.openai_ai_task"

    # Ensure entity is linked to the subentry
    entity_entry = entity_registry.async_get(entity_id)
    ai_task_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "ai_task_data"
        )
    )
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        create_image_gen_call_item(id="ig_A", output_index=0),
        create_message_item(id="msg_A", text="", output_index=1),
    ]

    assert hass.data[ai_task.DATA_IMAGES] == {}

    result = await ai_task.async_generate_image(
        hass,
        task_name="Test Task",
        entity_id="ai_task.openai_ai_task",
        instructions="Generate test image",
    )

    assert result["height"] == 1024
    assert result["width"] == 1536
    assert result["revised_prompt"] == "Mock revised prompt."
    assert result["mime_type"] == "image/png"
    assert result["model"] == "gpt-image-1"

    assert len(hass.data[ai_task.DATA_IMAGES]) == 1
    image_data = next(iter(hass.data[ai_task.DATA_IMAGES].values()))
    assert image_data.data == b"A"
    assert image_data.mime_type == "image/png"
    assert image_data.title == "Mock revised prompt."
