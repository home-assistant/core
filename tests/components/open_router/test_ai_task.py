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
from homeassistant.helpers.network import NoURLAvailableError

from . import setup_integration

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
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="The test data",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
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
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content='{"characters": ["Mario", "Luigi"]}',
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )
    )

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.gemini_1_5_pro",
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
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="INVALID JSON RESPONSE",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
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
    """Test AI Task raises HomeAssistantError when API returns empty choices."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(completion_tokens=0, prompt_tokens=8, total_tokens=8),
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
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Hi there!",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
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


async def test_generate_data_with_video_attachment_local(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task data generation with a local video attachment."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Video processed",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=2, prompt_tokens=8, total_tokens=10
            ),
        )
    )

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="/local/clip.mp4",
                mime_type="video/mp4",
                path=Path("/tmp/clip.mp4"),
            ),
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=b"fake_video_data"),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_1_5_pro",
            instructions="Describe the video",
            attachments=[{"media_content_id": "media-source://media_source/local/clip.mp4"}],
        )

    assert result.data == "Video processed"

    call_args = mock_openai_client.chat.completions.create.call_args
    user_message = call_args[1]["messages"][-2]
    assert user_message["content"] == [
        {"type": "text", "text": "Describe the video"},
        {
            "type": "video_url",
            "video_url": {"url": "data:video/mp4;base64,ZmFrZV92aWRlb19kYXRh"},
        },
    ]


async def test_generate_data_with_video_attachment_remote(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task data generation with a non-local video using a signed URL."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Video processed via URL",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="x-ai/grok-3",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=3, prompt_tokens=8, total_tokens=11
            ),
        )
    )

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                # First call: from ai_task._resolve_attachments
                media_source.PlayMedia(
                    url="/local/clip.mp4",
                    mime_type="video/mp4",
                    path=Path("/tmp/clip.mp4"),
                ),
                # Second call: from entity.py non-local video handler
                media_source.PlayMedia(
                    url="/local/clip.mp4",
                    mime_type="video/mp4",
                    path=Path("/tmp/clip.mp4"),
                ),
            ],
        ),
        patch("pathlib.Path.exists", return_value=False),
        patch(
            "homeassistant.components.open_router.entity.async_sign_path",
            return_value="/local/clip.mp4?authSig=xxx",
        ),
        patch(
            "homeassistant.components.open_router.entity.get_url",
            return_value="http://ha.example.com",
        ),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_1_5_pro",
            instructions="Describe the video",
            attachments=[{"media_content_id": "media-source://media_source/local/clip.mp4"}],
        )

    assert result.data == "Video processed via URL"

    call_args = mock_openai_client.chat.completions.create.call_args
    user_message = call_args[1]["messages"][-2]
    assert user_message["content"] == [
        {"type": "text", "text": "Describe the video"},
        {
            "type": "video_url",
            "video_url": {"url": "http://ha.example.com/local/clip.mp4?authSig=xxx"},
        },
    ]


async def test_generate_data_with_video_attachment_remote_no_external_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test that a HomeAssistantError is raised when no external URL is configured."""
    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="/local/clip.mp4",
                mime_type="video/mp4",
                path=Path("/tmp/clip.mp4"),
            ),
        ),
        patch("pathlib.Path.exists", return_value=False),
        patch(
            "homeassistant.components.open_router.entity.get_url",
            side_effect=NoURLAvailableError,
        ),
        pytest.raises(
            HomeAssistantError,
            match="An external URL must be configured to serve non-local video files to OpenRouter",
        ),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_1_5_pro",
            instructions="Describe the video",
            attachments=[{"media_content_id": "media-source://media_source/local/clip.mp4"}],
        )
