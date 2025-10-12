"""Test AI Task platform of OpenAI Conversation integration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import httpx
from openai import PermissionDeniedError
import pytest
import voluptuous as vol

from homeassistant.components import ai_task, media_source
from homeassistant.components.openai_conversation import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir, selector

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
                    url="http://example.com/context.pdf",
                    mime_type="application/pdf",
                    path=Path("context.pdf"),
                ),
            ],
        ),
        patch("pathlib.Path.exists", return_value=True),
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
                {"media_content_id": "media-source://media/context.pdf"},
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
            "filename": "context.pdf",
            "file_data": "data:application/pdf;base64,ZmFrZV9pbWFnZV9kYXRh",
            "type": "input_file",
        },
    ]


@pytest.mark.usefixtures("mock_init_component")
@freeze_time("2025-06-14 22:59:00")
@pytest.mark.parametrize("image_model", ["gpt-image-1", "gpt-image-1-mini"])
async def test_generate_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    image_model: str,
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
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        ai_task_entry,
        data={"image_model": image_model},
    )
    await hass.async_block_till_done()
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        create_image_gen_call_item(id="ig_A", output_index=0),
        create_message_item(id="msg_A", text="", output_index=1),
    ]

    with patch.object(
        media_source.local_source.LocalSource,
        "async_upload_media",
        return_value="media-source://ai_task/image/2025-06-14_225900_test_task.png",
    ) as mock_upload_media:
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
    assert result["model"] == image_model

    mock_upload_media.assert_called_once()
    image_data = mock_upload_media.call_args[0][1]
    assert image_data.file.getvalue() == b"A"
    assert image_data.content_type == "image/png"
    assert image_data.filename == "2025-06-14_225900_test_task.png"

    assert (
        issue_registry.async_get_issue(DOMAIN, "organization_verification_required")
        is None
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that repair issue is raised when verification is required."""
    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            side_effect=PermissionDeniedError(
                response=httpx.Response(
                    status_code=403, request=httpx.Request(method="GET", url="")
                ),
                body=None,
                message="Please click on Verify Organization.",
            ),
        ),
        pytest.raises(HomeAssistantError, match="Error talking to OpenAI"),
    ):
        await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test image",
        )

    assert issue_registry.async_get_issue(DOMAIN, "organization_verification_required")
