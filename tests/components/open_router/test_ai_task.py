"""Test AI Task structured data generation."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from openai import OpenAIError
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import (
    Choice as ChunkChoice,
    ChoiceDelta,
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import ai_task, media_source
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from . import setup_integration
from .conftest import get_generator_from_data


def _image_completion(
    images: list[dict[str, Any]] | None, content: str | None = None
) -> AsyncGenerator[ChatCompletionChunk]:
    """Build a streamed chat completion carrying generated images."""
    return get_generator_from_data(
        [
            ChatCompletionChunk.model_construct(
                id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                choices=[
                    ChunkChoice.model_construct(
                        finish_reason="stop",
                        index=0,
                        delta=ChoiceDelta(
                            content=content,
                            role="assistant",
                            images=images,
                        ),
                    )
                ],
                created=1700000000,
                model="google/gemini-2.5-flash-image",
                object="chat.completion.chunk",
                system_fingerprint=None,
            )
        ]
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

    entity_id = "ai_task.gemini_2_5_flash_image"

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
        entity_id="ai_task.gemini_2_5_flash_image",
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
    assert mock_openai_client.chat.completions.create.call_args.kwargs[
        "extra_body"
    ] == {"provider": {"require_parameters": True}}
    assert mock_openai_client.chat.completions.create.call_args_list[0][1][
        "response_format"
    ] == {
        "json_schema": {
            "name": "test_task",
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
            entity_id="ai_task.gemini_2_5_flash_image",
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

    with pytest.raises(
        HomeAssistantError, match="OpenRouter returned an empty response"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_2_5_flash_image",
            instructions="Generate test data",
        )


async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task data generation with attachments."""
    await setup_integration(hass, mock_config_entry)

    entity_id = "ai_task.gemini_2_5_flash_image"

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


@pytest.mark.parametrize(
    ("output_modalities", "supports_image"),
    [
        (["text", "image"], True),
        (["text"], False),
    ],
)
@pytest.mark.usefixtures("mock_openai_client")
async def test_generate_image_feature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    supports_image: bool,
) -> None:
    """Test GENERATE_IMAGE is advertised only for image-capable models."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("ai_task.gemini_2_5_flash_image")
    assert state is not None
    features = ai_task.AITaskEntityFeature(state.attributes["supported_features"])
    assert (ai_task.AITaskEntityFeature.GENERATE_IMAGE in features) is supports_image


async def test_generate_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task image generation."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_image_completion(
            [
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,aGVsbG8="},
                }
            ]
        )
    )

    with patch.object(
        media_source.local_source.LocalSource,
        "async_upload_media",
        return_value="media-source://ai_task/image/2025-06-14_225900_test_task.png",
    ) as mock_upload_media:
        result = await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_2_5_flash_image",
            instructions="Generate a test image",
        )

    assert result["mime_type"] == "image/png"
    assert result["model"] == "google/gemini-2.5-flash-image"

    image_data = mock_upload_media.call_args[0][1]
    assert image_data.file.getvalue() == b"hello"
    assert image_data.content_type == "image/png"

    call_kwargs = mock_openai_client.chat.completions.create.call_args[1]
    assert call_kwargs["extra_body"]["modalities"] == ["image", "text"]


async def test_generate_image_no_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task image generation raises when no image is returned."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_image_completion(None, content="I cannot generate that image")
    )

    with pytest.raises(HomeAssistantError, match="OpenRouter did not return an image"):
        await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_2_5_flash_image",
            instructions="Generate a test image",
        )


@pytest.mark.parametrize(
    "images",
    [
        pytest.param([{"type": "image_url"}], id="missing_url"),
        pytest.param(
            [{"type": "image_url", "image_url": {"url": "https://example.com/a.png"}}],
            id="not_a_data_uri",
        ),
        pytest.param(
            [{"type": "image_url", "image_url": {"url": "data:;base64,aGVsbG8="}}],
            id="empty_mime_type",
        ),
    ],
)
async def test_generate_image_invalid_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    images: list[dict[str, Any]],
) -> None:
    """Test AI Task image generation raises on a malformed image response."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_image_completion(images)
    )

    with pytest.raises(
        HomeAssistantError, match="OpenRouter returned an invalid image"
    ):
        await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_2_5_flash_image",
            instructions="Generate a test image",
        )


async def test_generate_data_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task raises when the API call fails."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=OpenAIError("boom")
    )

    with pytest.raises(
        HomeAssistantError,
        match="Error communicating with the OpenRouter API: boom",
    ) as exc_info:
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_2_5_flash_image",
            instructions="Generate test data",
        )
    assert exc_info.value.translation_key == "api_error"


async def test_generate_data_invalid_tool_arguments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test AI Task raises when the tool arguments are not valid JSON."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=get_generator_from_data(
            [
                ChatCompletionChunk.model_construct(
                    id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
                    choices=[
                        ChunkChoice.model_construct(
                            finish_reason="tool_calls",
                            index=0,
                            delta=ChoiceDelta(
                                role="assistant",
                                tool_calls=[
                                    ChoiceDeltaToolCall(
                                        index=0,
                                        id="call_call_1",
                                        type="function",
                                        function=ChoiceDeltaToolCallFunction(
                                            name="test_tool",
                                            arguments='{"param1"',
                                        ),
                                    )
                                ],
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
        HomeAssistantError, match="OpenRouter returned invalid tool arguments"
    ) as exc_info:
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_2_5_flash_image",
            instructions="Generate test data",
        )
    assert exc_info.value.translation_key == "tool_args_parse_error"


@pytest.mark.parametrize(
    ("exists", "mime_type", "translation_key", "message"),
    [
        pytest.param(
            False,
            "image/jpeg",
            "file_not_found",
            "`context.txt` does not exist",
            id="file_not_found",
        ),
        pytest.param(
            True,
            "text/plain",
            "unsupported_file_type",
            "Only images and PDF are supported by the OpenRouter API, "
            "`context.txt` is not an image file or PDF",
            id="unsupported_file_type",
        ),
    ],
)
@pytest.mark.usefixtures("mock_openai_client")
async def test_generate_data_invalid_attachment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exists: bool,
    mime_type: str,
    translation_key: str,
    message: str,
) -> None:
    """Test AI Task raises on attachments that cannot be sent."""
    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="http://example.com/context.txt",
                mime_type=mime_type,
                path=Path("context.txt"),
            ),
        ),
        patch("pathlib.Path.exists", return_value=exists),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_2_5_flash_image",
            instructions="Test prompt",
            attachments=[{"media_content_id": "media-source://media/context.txt"}],
        )
    assert exc_info.value.translation_key == translation_key
    assert str(exc_info.value) == message


@pytest.mark.parametrize(
    "generate",
    [
        pytest.param(ai_task.async_generate_data, id="generate_data"),
        pytest.param(ai_task.async_generate_image, id="generate_image"),
    ],
)
@pytest.mark.usefixtures("mock_openai_client")
async def test_response_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    generate: Callable[..., Awaitable[Any]],
) -> None:
    """Test AI Task raises when the chat log does not end with a response."""
    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.open_router.ai_task."
            "OpenRouterAITaskEntity._async_handle_chat_log",
        ),
        pytest.raises(
            HomeAssistantError,
            match="Last content in chat log is not an AssistantContent",
        ) as exc_info,
    ):
        await generate(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_2_5_flash_image",
            instructions="Test prompt",
        )
    assert exc_info.value.translation_key == "response_not_found"
