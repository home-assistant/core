"""Tests for the Anthropic integration."""

import base64
from collections.abc import Generator
import io
from json import JSONDecodeError
from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, patch

from anthropic import (
    AnthropicError,
    APIConnectionError,
    AuthenticationError,
    RateLimitError,
)
from anthropic.types import (
    Message,
    MessageDeltaUsage,
    RawMessageDeltaEvent,
    StopReason,
    TextBlock,
    Usage,
)
from anthropic.types.raw_message_delta_event import Delta
from freezegun import freeze_time
import httpx2
from PIL import Image
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import ai_task, media_source
from homeassistant.components.anthropic.const import (
    CONF_CHAT_MODEL,
    CONF_PROMPT_CACHING,
    DOMAIN,
    PromptCaching,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.setup import async_setup_component

from . import create_content_block, create_server_tool_use_block, create_thinking_block


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation."""
    entity_id = "ai_task.claude_ai_task"

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

    mock_create_stream.return_value = [create_content_block(0, ["The test data"])]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        instructions="Generate test data",
    )

    assert result.data == "The test data"


@pytest.mark.usefixtures("mock_init_component")
async def test_translation_key(
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entity translation key."""
    entry = entity_registry.async_get("ai_task.claude_ai_task")
    assert entry is not None
    assert entry.translation_key == "ai_task_data"


@pytest.mark.usefixtures("mock_init_component")
async def test_empty_data(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Test a completed empty response returns empty data."""
    mock_create_stream.return_value = [create_content_block(0, [""])]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.claude_ai_task",
        instructions="Generate test data",
    )

    assert result.data == ""


@pytest.mark.usefixtures("mock_init_component")
async def test_missing_response(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Test a stream without a response still raises an error."""
    mock_create_stream.side_effect = None
    mock_create_stream.return_value = AsyncMock()
    mock_create_stream.return_value.__aiter__.return_value = []

    with pytest.raises(
        HomeAssistantError, match="Last content in chat log is not an AssistantContent"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.claude_ai_task",
            instructions="Generate test data",
        )


@pytest.mark.usefixtures("mock_init_component")
async def test_stream_wrong_type(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Test error if the response is not a stream."""
    mock_create_stream.return_value = Message(
        type="message",
        id="message_id",
        model="claude-fable-5",
        role="assistant",
        content=[TextBlock(type="text", text="This is not a stream")],
        usage=Usage(input_tokens=42, output_tokens=42),
    )

    with pytest.raises(HomeAssistantError, match="Expected a stream of messages"):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.claude_ai_task",
            instructions="Generate test data",
        )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("stop_reason", "translation_key", "message"),
    [
        pytest.param(
            "max_tokens",
            "response_max_tokens",
            "Claude reached the output token limit before completing the response",
            id="max_tokens",
        ),
        pytest.param(
            "model_context_window_exceeded",
            "response_context_window_exceeded",
            "Claude reached the context window limit before completing the response",
            id="context_window_exceeded",
        ),
        pytest.param(
            "refusal",
            "api_refusal",
            "Potential policy violation detected",
            id="refusal",
        ),
        pytest.param(
            "stop_sequence",
            "response_stop_sequence",
            "Claude stopped after encountering a stop sequence",
            id="stop_sequence",
        ),
    ],
)
@pytest.mark.parametrize(
    ("structure", "response_text"),
    [
        pytest.param(None, "The generated data starts with", id="plain"),
        pytest.param(
            probatio.Schema(
                {
                    probatio.Required("characters"): selector.selector(
                        {"text": {"multiple": True}}
                    )
                }
            ),
            '{"characters": ["Mario',
            id="structured",
        ),
    ],
)
async def test_generate_data_stop_reason_error(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
    stop_reason: StopReason,
    translation_key: str,
    message: str,
    structure: probatio.Schema | None,
    response_text: str,
) -> None:
    """Reject unsuccessful stop reasons before parsing structured data."""
    mock_create_stream.return_value = [
        [
            *create_content_block(0, [response_text]),
            RawMessageDeltaEvent(
                type="message_delta",
                delta=Delta(stop_reason=stop_reason),
                usage=MessageDeltaUsage(output_tokens=10),
            ),
        ]
    ]

    with pytest.raises(HomeAssistantError, match=re.escape(message)) as exc_info:
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.claude_ai_task",
            instructions="Generate test data",
            structure=structure,
        )

    assert exc_info.value.translation_key == translation_key
    mock_create_stream.assert_awaited_once()


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_invalid_tool_arguments(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Report invalid tool arguments with the first parsing error as the cause."""
    incomplete_json = '{"command": "echo'
    mock_create_stream.return_value = [
        [
            *create_server_tool_use_block(
                0, "srvtoolu_first", "bash_code_execution", [incomplete_json]
            ),
            *create_server_tool_use_block(
                1, "srvtoolu_second", "bash_code_execution", ['{"command":']
            ),
        ]
    ]

    with pytest.raises(
        HomeAssistantError, match="Claude returned invalid tool arguments"
    ) as exc_info:
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.claude_ai_task",
            instructions="Generate test data",
        )

    assert exc_info.value.translation_key == "tool_args_parse_error"
    assert isinstance(exc_info.value.__cause__, JSONDecodeError)
    assert exc_info.value.__cause__.doc == incomplete_json
    mock_create_stream.assert_awaited_once()


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_invalid_structured_data(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Test AI Task with an invalid JSON response."""
    mock_create_stream.return_value = [
        create_content_block(0, ["INVALID JSON RESPONSE"])
    ]

    with pytest.raises(
        HomeAssistantError, match="Error with Claude structured response"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.claude_ai_task",
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


@freeze_time("2026-01-01 12:00:00")
@pytest.mark.usefixtures("mock_init_component")
async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test AI Task structured data generation."""
    mock_create_stream.return_value = [
        create_content_block(0, ['{"charac', 'ters": ["Mario', '", "Luigi"]}'])
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.claude_ai_task",
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
    assert mock_create_stream.call_args.kwargs.copy() == snapshot


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Test AI Task data generation with attachments."""
    entity_id = "ai_task.claude_ai_task"

    mock_create_stream.return_value = [create_content_block(0, ["Hi there!"])]

    # Test with attachments
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpg",
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

    # Verify that the create stream was called with the correct parameters
    # The last call should have the user message with attachments
    call_args = mock_create_stream.call_args
    assert call_args is not None

    # Check that the input includes the attachments
    input_messages = call_args[1]["messages"]
    assert len(input_messages) > 0

    # Find the user message with attachments
    user_message_with_attachments = input_messages[-2]

    assert user_message_with_attachments is not None
    assert isinstance(user_message_with_attachments["content"], list)
    assert len(user_message_with_attachments["content"]) == 3  # Text + attachments

    text_block, image_block, document_block = user_message_with_attachments["content"]

    # Text block
    assert text_block["type"] == "text"
    assert text_block["text"] == "Test prompt"

    # Image attachment
    assert image_block["type"] == "image"
    assert image_block["source"] == {
        "data": "ZmFrZV9pbWFnZV9kYXRh",
        "media_type": "image/jpeg",
        "type": "base64",
    }

    # Document attachment (ignore extra metadata like cache_control)
    assert document_block["type"] == "document"
    assert document_block["source"]["data"] == "ZmFrZV9pbWFnZV9kYXRh"
    assert document_block["source"]["media_type"] == "application/pdf"
    assert document_block["source"]["type"] == "base64"


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_invalid_attachments(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Test AI Task data generation with attachments of unsupported type."""
    entity_id = "ai_task.claude_ai_task"

    mock_create_stream.return_value = [create_content_block(0, ["Hi there!"])]

    # Test path that doesn't exist
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpeg",
                    path=Path("doorbell_snapshot.jpg"),
                )
            ],
        ),
        patch("pathlib.Path.exists", return_value=False),
        pytest.raises(
            HomeAssistantError, match="`doorbell_snapshot.jpg` does not exist"
        ),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
            ],
        )

    # Test unsupported file type
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.txt",
                    mime_type=None,
                    path=Path("doorbell_snapshot.txt"),
                )
            ],
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "homeassistant.components.anthropic.entity.guess_file_type",
            return_value=("text/plain", None),
        ),
        pytest.raises(
            HomeAssistantError,
            match=re.escape(
                "The Claude Haiku 5.5 model does not support"
                " text/plain file types"
                " (for `doorbell_snapshot.txt`)"
            ),
        ),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.txt"},
            ],
        )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_with_attachments_whitespace_instructions(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
) -> None:
    """Test whitespace-only instructions with attachments produce no text block.

    The API rejects whitespace-only text blocks, so the user message should
    contain only the attachment.
    """
    entity_id = "ai_task.claude_ai_task"

    mock_create_stream.return_value = [create_content_block(0, ["Hi there!"])]

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpg",
                    path=Path("doorbell_snapshot.jpg"),
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
            instructions=" ",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
            ],
        )

    assert result.data == "Hi there!"

    input_messages = mock_create_stream.call_args[1]["messages"]
    user_message = input_messages[-2]
    assert user_message["role"] == "user"
    assert isinstance(user_message["content"], list)
    assert [block["type"] for block in user_message["content"]] == ["image"]


CLASSIFY_ENTITY_ID = "ai_task.claude_ai_task"
API_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
CLASSIFY_IMAGE = {
    "media_content_id": "media-source://camera/camera.garage",
    "media_content_type": "image/jpeg",
}


def _example(name: str) -> dict[str, str]:
    return {
        "media_content_id": f"media-source://media_source/local/garage/{name}",
        "media_content_type": "image/jpeg",
    }


CLASSIFY_LABELS = {
    "empty": {
        "description": "The bay is empty",
        "examples": [_example("empty_1"), _example("empty_2")],
    },
    "car": {"examples": [_example("car_1")]},
}


@pytest.fixture
def mock_media_image() -> Generator[AsyncMock]:
    """Return every media source as an image holding the last part of its ID."""

    async def get_image(
        hass: HomeAssistant, media_content_id: str
    ) -> media_source.MediaImage:
        return media_source.MediaImage(
            mime_type="image/jpeg", content=media_content_id.rpartition("/")[2].encode()
        )

    with patch(
        "homeassistant.components.media_source.async_get_media_image",
        side_effect=get_image,
    ) as mock:
        yield mock


@pytest.fixture
def mock_crop_image(mock_media_image: AsyncMock) -> Generator[AsyncMock]:
    """Pass image contents through instead of decoding them."""
    with patch(
        "homeassistant.components.ai_task.crop_image",
        side_effect=lambda path, region: path.read_bytes(),
    ) as mock:
        yield mock


@pytest.fixture
def classify_stream(mock_create_stream: AsyncMock) -> AsyncMock:
    """Answer image classifications with a label."""
    mock_create_stream.return_value = [
        create_content_block(0, ['{"label": "car", "unsure": false}'])
    ]
    return mock_create_stream


def _set_ai_task_options(
    hass: HomeAssistant, entry: MockConfigEntry, data: dict[str, str]
) -> None:
    hass.config_entries.async_update_subentry(
        entry,
        next(
            subentry
            for subentry in entry.subentries.values()
            if subentry.subentry_type == "ai_task_data"
        ),
        data=data,
    )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("instructions", "region", "expected_region"),
    [
        pytest.param(None, None, None, id="defaults"),
        pytest.param(
            "Is a car parked in the left bay?",
            {"left": 0.5, "top": 0.25},
            ai_task.Region(left=0.5, top=0.25),
            id="instructions-and-region",
        ),
    ],
)
async def test_classify_image(
    hass: HomeAssistant,
    classify_stream: AsyncMock,
    mock_crop_image: AsyncMock,
    instructions: str | None,
    region: dict[str, float] | None,
    expected_region: ai_task.Region | None,
    snapshot: SnapshotAssertion,
) -> None:
    """Send the examples of each label before the image to classify."""
    result = await ai_task.async_classify_image(
        hass,
        task_name="Left garage bay",
        entity_id=CLASSIFY_ENTITY_ID,
        image=CLASSIFY_IMAGE,
        labels=CLASSIFY_LABELS,
        region=region,
        instructions=instructions,
    )
    assert result == ai_task.ClassifyImageTaskResult(label="car", probabilities=None)
    assert classify_stream.call_args.kwargs == snapshot
    assert [call.args[1] for call in mock_crop_image.call_args_list] == [
        expected_region
    ] * 4


@pytest.mark.usefixtures("mock_init_component", "mock_crop_image")
@pytest.mark.parametrize(
    ("labels", "answer", "label"),
    [
        pytest.param(
            CLASSIFY_LABELS, '{"label": "empty", "unsure": false}', "empty", id="empty"
        ),
        pytest.param(
            CLASSIFY_LABELS, '{"label": "car", "unsure": false}', "car", id="car"
        ),
        pytest.param(
            CLASSIFY_LABELS, '{"label": "car", "unsure": true}', None, id="unsure"
        ),
        pytest.param(
            {
                "unsure": {"examples": [_example("unsure_1")]},
                "car": {"examples": [_example("car_1")]},
            },
            '{"label": "unsure", "unsure": false}',
            "unsure",
            id="label-named-unsure",
        ),
    ],
)
async def test_classify_image_label(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
    labels: dict[str, dict[str, Any]],
    answer: str,
    label: str | None,
) -> None:
    """Return the chosen label, or none when Claude is unsure."""
    mock_create_stream.return_value = [
        [
            *create_thinking_block(0, ["The bay looks"]),
            *create_content_block(1, [answer[:10], answer[10:]]),
        ]
    ]
    result = await ai_task.async_classify_image(
        hass,
        task_name="Left garage bay",
        entity_id=CLASSIFY_ENTITY_ID,
        image=CLASSIFY_IMAGE,
        labels=labels,
    )
    assert result == ai_task.ClassifyImageTaskResult(label=label, probabilities=None)


@pytest.mark.usefixtures("mock_crop_image")
async def test_classify_image_without_prompt_caching(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    classify_stream: AsyncMock,
) -> None:
    """Mark no cache breakpoint when prompt caching is off."""
    _set_ai_task_options(
        hass, mock_config_entry, {CONF_PROMPT_CACHING: PromptCaching.OFF}
    )
    await hass.async_block_till_done()
    await ai_task.async_classify_image(
        hass,
        task_name="Left garage bay",
        entity_id=CLASSIFY_ENTITY_ID,
        image=CLASSIFY_IMAGE,
        labels=CLASSIFY_LABELS,
    )
    content = classify_stream.call_args.kwargs["messages"][0]["content"]
    assert [block for block in content if "cache_control" in block] == []


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("examples", "source_size", "expected_size"),
    [
        pytest.param(19, (4400, 400), (2200, 200), id="up-to-20-images"),
        pytest.param(20, (4400, 400), (2000, 182), id="many-images"),
        pytest.param(20, (1000, 500), (500, 250), id="many-small-images"),
    ],
)
async def test_classify_image_crop(
    hass: HomeAssistant,
    classify_stream: AsyncMock,
    examples: int,
    source_size: tuple[int, int],
    expected_size: tuple[int, int],
) -> None:
    """Send every image as a JPEG cropped to the region and fit for many images."""
    image = io.BytesIO()
    Image.new("RGB", source_size).save(image, format="PNG")
    labels = {
        "empty": {"examples": [_example("empty_1")]},
        "car": {"examples": [_example("car_1")] * (examples - 1)},
    }
    with patch(
        "homeassistant.components.media_source.async_get_media_image",
        return_value=media_source.MediaImage(
            mime_type="image/png", content=image.getvalue()
        ),
    ):
        await ai_task.async_classify_image(
            hass,
            task_name="Left garage bay",
            entity_id=CLASSIFY_ENTITY_ID,
            image=CLASSIFY_IMAGE,
            labels=labels,
            region={"left": 0.5, "bottom": 0.5},
        )
    content = classify_stream.call_args.kwargs["messages"][0]["content"]
    images = [
        Image.open(io.BytesIO(base64.b64decode(block["source"]["data"])))
        for block in content
        if block["type"] == "image"
    ]
    assert [(image.format, image.size) for image in images] == [
        ("JPEG", expected_size)
    ] * (examples + 1)


@pytest.mark.parametrize(
    ("model", "examples", "max_images"),
    [
        pytest.param("claude-haiku-5-5", 600, "600", id="1m-context"),
        pytest.param("claude-haiku-4-5", 100, "100", id="200k-context"),
    ],
)
async def test_classify_image_too_many_images(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_model_list: AsyncMock,
    mock_create_stream: AsyncMock,
    mock_crop_image: AsyncMock,
    model: str,
    examples: int,
    max_images: str,
) -> None:
    """Reject more images than the API accepts in one request."""
    _set_ai_task_options(hass, mock_config_entry, {CONF_CHAT_MODEL: model})
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    labels = {
        "empty": {"examples": [_example("empty_1")]},
        "car": {"examples": [_example("car_1")] * (examples - 1)},
    }
    with pytest.raises(ServiceValidationError) as exc_info:
        await ai_task.async_classify_image(
            hass,
            task_name="Left garage bay",
            entity_id=CLASSIFY_ENTITY_ID,
            image=CLASSIFY_IMAGE,
            labels=labels,
        )
    assert exc_info.value.translation_key == "too_many_classification_images"
    assert exc_info.value.translation_placeholders == {
        "images": str(examples + 1),
        "max_images": max_images,
    }
    mock_crop_image.assert_not_called()
    mock_create_stream.assert_not_called()


@pytest.mark.usefixtures("mock_init_component", "mock_crop_image")
@pytest.mark.parametrize(
    ("text", "stop_reason", "translation_key"),
    [
        pytest.param("It is a car", "end_turn", "json_parse_error", id="not-json"),
        pytest.param(
            '["car"]', "end_turn", "classification_not_found", id="not-object"
        ),
        pytest.param(
            '{"label": "car"}', "end_turn", "classification_not_found", id="no-unsure"
        ),
        pytest.param(
            '{"label": "car", "unsure": "no"}',
            "end_turn",
            "classification_not_found",
            id="unsure-not-boolean",
        ),
        pytest.param(
            '{"label": "bike", "unsure": false}',
            "end_turn",
            "classification_not_found",
            id="label-outside-enum",
        ),
        pytest.param(
            '{"label": ["car"], "unsure": false}',
            "end_turn",
            "classification_not_found",
            id="label-not-a-string",
        ),
        pytest.param("", "refusal", "api_refusal", id="refusal"),
        pytest.param(
            '{"label": "c', "max_tokens", "response_max_tokens", id="max-tokens"
        ),
    ],
)
async def test_classify_image_invalid_responses(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
    text: str,
    stop_reason: StopReason,
    translation_key: str,
) -> None:
    """Report refusals and missing or malformed labels as errors."""
    mock_create_stream.return_value = [
        [
            *create_content_block(0, [text]),
            RawMessageDeltaEvent(
                type="message_delta",
                delta=Delta(stop_reason=stop_reason),
                usage=MessageDeltaUsage(output_tokens=10),
            ),
        ]
    ]
    with pytest.raises(HomeAssistantError) as exc_info:
        await ai_task.async_classify_image(
            hass,
            task_name="Left garage bay",
            entity_id=CLASSIFY_ENTITY_ID,
            image=CLASSIFY_IMAGE,
            labels=CLASSIFY_LABELS,
        )
    assert exc_info.value.translation_key == translation_key


@pytest.mark.usefixtures("mock_init_component", "mock_crop_image")
@pytest.mark.parametrize(
    ("error", "translation_key", "message"),
    [
        pytest.param(
            AuthenticationError(
                message="invalid x-api-key",
                response=httpx2.Response(status_code=401, request=API_REQUEST),
                body=None,
            ),
            "api_authentication_error",
            "invalid x-api-key",
            id="authentication",
        ),
        pytest.param(
            APIConnectionError(request=API_REQUEST),
            "api_error",
            "Connection error.",
            id="connection",
        ),
        pytest.param(
            RateLimitError(
                message="rate limited",
                response=httpx2.Response(status_code=429, request=API_REQUEST),
                body=None,
            ),
            "api_error",
            "rate limited",
            id="api-status",
        ),
        pytest.param(AnthropicError("broken"), "api_error", "broken", id="other"),
    ],
)
async def test_classify_image_api_error(
    hass: HomeAssistant,
    mock_create_stream: AsyncMock,
    error: AnthropicError,
    translation_key: str,
    message: str,
) -> None:
    """Translate SDK errors into Home Assistant errors."""
    mock_create_stream.side_effect = error
    with pytest.raises(HomeAssistantError) as exc_info:
        await ai_task.async_classify_image(
            hass,
            task_name="Left garage bay",
            entity_id=CLASSIFY_ENTITY_ID,
            image=CLASSIFY_IMAGE,
            labels=CLASSIFY_LABELS,
        )
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {"message": message}


@pytest.mark.usefixtures("mock_init_component", "mock_media_image")
async def test_classify_image_unreadable(
    hass: HomeAssistant, mock_create_stream: AsyncMock
) -> None:
    """Report images that cannot be decoded as errors."""
    with pytest.raises(HomeAssistantError) as exc_info:
        await ai_task.async_classify_image(
            hass,
            task_name="Left garage bay",
            entity_id=CLASSIFY_ENTITY_ID,
            image=CLASSIFY_IMAGE,
            labels=CLASSIFY_LABELS,
        )
    assert exc_info.value.translation_key == "classification_image_unreadable"
    mock_create_stream.assert_not_called()
