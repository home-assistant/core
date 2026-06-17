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


def _image_completion(
    images: list[dict] | None, content: str | None = None
) -> ChatCompletion:
    """Build a chat completion carrying generated images."""
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
                    images=images,
                ),
            )
        ],
        created=1700000000,
        model="google/gemini-2.5-flash-image",
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
        entity_id="ai_task.gemini_2_5_flash_image",
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
            entity_id="ai_task.gemini_2_5_flash_image",
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
async def test_generate_image_feature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
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

    with pytest.raises(HomeAssistantError, match="No image returned"):
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
    images: list[dict],
) -> None:
    """Test AI Task image generation raises on a malformed image response."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_image_completion(images)
    )

    with pytest.raises(HomeAssistantError, match="Invalid image returned"):
        await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.gemini_2_5_flash_image",
            instructions="Generate a test image",
        )
