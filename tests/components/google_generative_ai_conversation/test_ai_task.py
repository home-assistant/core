"""Test AI Task platform of Google Generative AI Conversation integration."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from freezegun import freeze_time
from google.genai.types import File, FileState, GenerateContentResponse
import pytest
import voluptuous as vol

from homeassistant.components import ai_task, media_source
from homeassistant.components.google_generative_ai_conversation.const import (
    RECOMMENDED_IMAGE_MODEL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from tests.common import MockConfigEntry
from tests.components.conversation import (
    MockChatLog,
    mock_chat_log,  # noqa: F401
)


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
    mock_chat_create: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test generating data."""
    entity_id = "ai_task.google_ai_task"

    # Ensure it's linked to the subentry
    entity_entry = entity_registry.async_get(entity_id)
    ai_task_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "ai_task_data"
        )
    )
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    mock_send_message_stream.return_value = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [{"text": "Hi there!"}],
                            "role": "model",
                        },
                    }
                ],
            ),
        ],
    ]
    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        instructions="Test prompt",
    )
    assert result.data == "Hi there!"

    # Test with attachments
    mock_send_message_stream.return_value = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [{"text": "Hi there!"}],
                            "role": "model",
                        },
                    }
                ],
            ),
        ],
    ]
    file1 = File(name="doorbell_snapshot.jpg", state=FileState.ACTIVE)
    file2 = File(name="context.txt", state=FileState.ACTIVE)
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
        patch(
            "google.genai.files.Files.upload",
            side_effect=[file1, file2],
        ) as mock_upload,
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("mimetypes.guess_type", return_value=["image/jpeg"]),
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

    outgoing_message = mock_send_message_stream.mock_calls[1][2]["message"]
    assert outgoing_message == ["Test prompt", file1, file2]

    assert result.data == "Hi there!"
    assert len(mock_upload.mock_calls) == 2
    assert mock_upload.mock_calls[0][2]["file"] == Path("doorbell_snapshot.jpg")
    assert mock_upload.mock_calls[1][2]["file"] == Path("context.txt")

    # Test attachments require play media with a path
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpeg",
                    path=None,
                ),
            ],
        ),
        pytest.raises(
            HomeAssistantError, match="Only local attachments are currently supported"
        ),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
            ],
        )

    # Test with structure
    mock_send_message_stream.return_value = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [{"text": '{"characters": ["Mario", "Luigi"]}'}],
                            "role": "model",
                        },
                    }
                ],
            ),
        ],
    ]
    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        instructions="Give me 2 mario characters",
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

    assert len(mock_chat_create.mock_calls) == 3
    config = mock_chat_create.mock_calls[-1][2]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema == {
        "properties": {"characters": {"items": {"type": "STRING"}, "type": "ARRAY"}},
        "required": ["characters"],
        "type": "OBJECT",
    }
    # Raise error on invalid JSON response
    mock_send_message_stream.return_value = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "parts": [{"text": "INVALID JSON RESPONSE"}],
                            "role": "model",
                        },
                    }
                ],
            ),
        ],
    ]
    with pytest.raises(HomeAssistantError):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            structure=vol.Schema({vol.Required("bla"): str}),
        )


@pytest.mark.usefixtures("mock_init_component")
@freeze_time("2025-06-14 22:59:00")
async def test_generate_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_generate_content: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task image generation."""
    mock_image_data = b"fake_image_data"
    mock_generate_content.return_value = Mock(
        text="Here is your generated image",
        prompt_feedback=None,
        candidates=[
            Mock(
                content=Mock(
                    parts=[
                        Mock(
                            text="Here is your generated image",
                            inline_data=None,
                            thought=False,
                        ),
                        Mock(
                            inline_data=Mock(
                                data=mock_image_data, mime_type="image/png"
                            ),
                            text=None,
                            thought=False,
                        ),
                    ]
                )
            )
        ],
    )

    with patch.object(
        media_source.local_source.LocalSource,
        "async_upload_media",
        return_value="media-source://ai_task/image/2025-06-14_225900_test_task.png",
    ) as mock_upload_media:
        result = await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.google_ai_task",
            instructions="Generate a test image",
        )

    assert result["height"] is None
    assert result["width"] is None
    assert result["revised_prompt"] == "Generate a test image"
    assert result["mime_type"] == "image/png"
    assert result["model"] == RECOMMENDED_IMAGE_MODEL.partition("/")[-1]

    mock_upload_media.assert_called_once()
    image_data = mock_upload_media.call_args[0][1]
    assert image_data.file.getvalue() == mock_image_data
    assert image_data.content_type == "image/png"
    assert image_data.filename == "2025-06-14_225900_test_task.png"

    # Verify that generate_content was called with correct parameters
    assert mock_generate_content.called
    call_args = mock_generate_content.call_args
    assert call_args.kwargs["model"] == RECOMMENDED_IMAGE_MODEL
    assert call_args.kwargs["contents"] == ["Generate a test image"]
    assert call_args.kwargs["config"].response_modalities == ["TEXT", "IMAGE"]
