"""Test AI Task platform of Azure OpenAI integration."""

from collections.abc import Awaitable, Callable
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
from openai import AuthenticationError
import probatio
import pytest

from homeassistant.components import ai_task, conversation, media_source
from homeassistant.components.azure_openai.ai_task import OpenAITaskEntity
from homeassistant.components.azure_openai.capabilities import RECOMMENDED_IMAGE_MODEL
from homeassistant.components.azure_openai.const import (
    CONF_CHAT_MODEL,
    CONF_IMAGE_DEPLOYMENT,
    CONF_IMAGE_MODEL,
    CONF_MODEL_FAMILY,
    CONF_VERBOSITY,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

from . import create_image_gen_call_item, create_message_item, create_reasoning_item

from tests.common import MockConfigEntry

AI_TASK_ENTITY_ID = "ai_task.azure_openai_ai_task"


@pytest.fixture
def ai_task_entity(hass: HomeAssistant) -> Any:
    """Return the Azure OpenAI AI Task entity."""
    return hass.data[ai_task.DOMAIN].get_entity(AI_TASK_ENTITY_ID)


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation."""
    entity_id = AI_TASK_ENTITY_ID

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
    assert mock_create_stream.call_args is not None
    assert (
        mock_create_stream.call_args.kwargs["model"]
        == ai_task_entry.data[CONF_CHAT_MODEL]
    )
    assert mock_create_stream.call_args.kwargs["store"] is False
    assert (
        mock_create_stream.call_args.kwargs["prompt_cache_key"]
        == ai_task_entry.subentry_id
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_authentication_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
) -> None:
    """Test AI Task authentication failures start reauthentication."""
    mock_create_stream.return_value = [
        AuthenticationError(
            response=httpx.Response(status_code=401, request=""),
            body=None,
            message=None,
        )
    ]

    with (
        patch.object(mock_config_entry, "async_start_reauth") as mock_reauth,
        pytest.raises(HomeAssistantError),
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=AI_TASK_ENTITY_ID,
            instructions="Generate test data",
        )

    mock_reauth.assert_called_once_with(hass)


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("model_family", "verbosity", "expected_verbosity"),
    [
        pytest.param("gpt-4o-mini", "low", None, id="without-verbosity"),
        pytest.param("gpt-5-mini", "low", "low", id="low-verbosity"),
        pytest.param("gpt-5-mini", "high", "high", id="high-verbosity"),
    ],
)
async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    model_family: str,
    verbosity: str,
    expected_verbosity: str | None,
) -> None:
    """Test AI Task structured data generation."""
    ai_task_entry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "ai_task_data"
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        ai_task_entry,
        data={
            **ai_task_entry.data,
            CONF_MODEL_FAMILY: model_family,
            CONF_VERBOSITY: verbosity,
        },
    )
    await hass.async_block_till_done()

    mock_create_stream.return_value = [
        create_message_item(
            id="msg_A", text='{"characters": ["Mario", "Luigi"]}', output_index=0
        )
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=AI_TASK_ENTITY_ID,
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
    assert mock_create_stream.call_args is not None
    assert (
        mock_create_stream.call_args.kwargs["model"]
        == ai_task_entry.data[CONF_CHAT_MODEL]
    )
    text = mock_create_stream.call_args.kwargs["text"]
    assert text["format"]["strict"] is True
    assert text.get("verbosity") == expected_verbosity


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_invalid_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test AI Task with invalid JSON response."""
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="INVALID JSON RESPONSE", output_index=0)
    ]

    with pytest.raises(HomeAssistantError) as err:
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=AI_TASK_ENTITY_ID,
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

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "invalid_structured_response"
    azure_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("homeassistant.components.azure_openai")
    )
    assert "Failed to parse JSON response" in azure_logs
    assert "INVALID JSON RESPONSE" not in azure_logs

    ai_task_entry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "ai_task_data"
    )
    assert mock_create_stream.call_args is not None
    assert (
        mock_create_stream.call_args.kwargs["model"]
        == ai_task_entry.data[CONF_CHAT_MODEL]
    )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("generate", "task"),
    [
        pytest.param(
            OpenAITaskEntity._async_generate_data,
            ai_task.GenDataTask(name="Task", instructions="Generate"),
            id="data",
        ),
        pytest.param(
            OpenAITaskEntity._async_generate_image,
            ai_task.GenImageTask(name="Task", instructions="Generate"),
            id="image",
        ),
    ],
)
async def test_generation_requires_assistant_content(
    hass: HomeAssistant,
    ai_task_entity: Any,
    generate: Callable[..., Awaitable[Any]],
    task: ai_task.GenDataTask | ai_task.GenImageTask,
) -> None:
    """Test generated results require assistant content."""
    chat_log = conversation.ChatLog(hass, "conversation-id")
    chat_log.async_add_user_content(conversation.UserContent(content="Generate"))

    with (
        patch.object(ai_task_entity, "_async_handle_chat_log", new=AsyncMock()),
        pytest.raises(HomeAssistantError) as err,
    ):
        await generate(ai_task_entity, task, chat_log)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "unexpected_chat_log_content"


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_image_requires_image_result(
    hass: HomeAssistant,
    ai_task_entity: Any,
) -> None:
    """Test image generation requires an image result."""
    chat_log = conversation.ChatLog(hass, "conversation-id")

    async def add_assistant_content(*_args: Any, **_kwargs: Any) -> None:
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=AI_TASK_ENTITY_ID,
                content="No image was generated",
            )
        )

    with (
        patch.object(
            ai_task_entity,
            "_async_handle_chat_log",
            new=AsyncMock(side_effect=add_assistant_content),
        ),
        pytest.raises(HomeAssistantError) as err,
    ):
        await ai_task_entity._async_generate_image(
            ai_task.GenImageTask(name="Task", instructions="Generate"),
            chat_log,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "no_image_returned"


@pytest.fixture
def selection_structure() -> probatio.Schema:
    """A multi-select with optional fields represented as null on the wire."""
    return probatio.Schema(
        {
            probatio.Optional("names"): selector.SelectSelector(
                {"options": ["a", "b"], "multiple": True}
            ),
            probatio.Optional("label"): selector.TextSelector(),
        }
    )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    "names",
    [
        pytest.param(["a", "b"], id="selection"),
        pytest.param(["a", "a"], id="duplicates"),
        pytest.param(None, id="omitted"),
    ],
)
async def test_generate_selection(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_create_stream: AsyncMock,
    selection_structure: probatio.Schema,
    names: list[str] | None,
) -> None:
    """Generate multi-select results while accepting duplicates and optional nulls."""
    data = {"names": names, "label": None}
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text=json.dumps(data), output_index=0)
    ]
    result = await ai_task.async_generate_data(
        hass,
        task_name="Selection",
        entity_id=AI_TASK_ENTITY_ID,
        instructions="Select names",
        structure=selection_structure,
    )
    assert result.data == data
    schema = mock_create_stream.call_args.kwargs["text"]["format"]["schema"]
    assert "uniqueItems" not in schema["properties"]["names"]
    assert (
        "Removed unsupported uniqueItems: true from OpenAI output schema at $.properties.names"
        in caplog.text
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation with attachments."""
    entity_id = AI_TASK_ENTITY_ID

    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hi there!", output_index=0)
    ]

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
            "homeassistant.components.azure_openai.entity.guess_file_type",
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

    ai_task_entry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "ai_task_data"
    )

    call_args = mock_create_stream.call_args
    assert call_args is not None

    assert call_args.kwargs["model"] == ai_task_entry.data[CONF_CHAT_MODEL]
    input_messages = call_args[1]["input"]
    assert len(input_messages) > 0

    user_message_with_attachments = input_messages[-2]

    assert user_message_with_attachments is not None
    assert isinstance(user_message_with_attachments["content"], list)
    assert len(user_message_with_attachments["content"]) == 3
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
@pytest.mark.freeze_time("2025-06-14 22:59:00")
@pytest.mark.parametrize(
    ("image_options", "image_model"),
    [
        ({}, RECOMMENDED_IMAGE_MODEL),
        ({CONF_IMAGE_MODEL: "gpt-image-1.5"}, "gpt-image-1.5"),
        ({CONF_IMAGE_MODEL: "gpt-image-1"}, "gpt-image-1"),
        ({CONF_IMAGE_MODEL: "gpt-image-1-mini"}, "gpt-image-1-mini"),
    ],
)
async def test_generate_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
    image_options: dict[str, str],
    image_model: str,
) -> None:
    """Test AI Task image generation."""
    entity_id = AI_TASK_ENTITY_ID
    image_deployment = "custom-image-deployment"

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
        data={
            **ai_task_entry.data,
            **image_options,
            CONF_IMAGE_DEPLOYMENT: image_deployment,
        },
    )
    await hass.async_block_till_done()
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    mock_create_stream.return_value = [
        (
            *create_reasoning_item(
                id="rs_A",
                output_index=0,
                reasoning_summary=[["The user asks me to generate an image"]],
            ),
            *create_image_gen_call_item(id="ig_A", output_index=1),
            *create_message_item(id="msg_A", text="", output_index=2),
        )
    ]

    with patch.object(
        media_source.local_source.LocalSource,
        "async_upload_media",
        return_value="media-source://ai_task/image/2025-06-14_155900_test_task.png",
    ) as mock_upload_media:
        result = await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id=AI_TASK_ENTITY_ID,
            instructions="Generate test image",
        )

    assert result["height"] == 1024
    assert result["width"] == 1536
    assert result["revised_prompt"] == "Mock revised prompt."
    assert result["mime_type"] == "image/png"
    assert result["model"] == image_model

    mock_upload_media.assert_called_once()
    assert mock_create_stream.call_args is not None
    assert (
        mock_create_stream.call_args.kwargs["model"]
        == ai_task_entry.data[CONF_CHAT_MODEL]
    )
    assert mock_create_stream.call_args.kwargs["store"] is True
    image_tool = next(
        iter(
            tool
            for tool in mock_create_stream.call_args.kwargs["tools"]
            if tool["type"] == "image_generation"
        ),
    )
    assert image_tool == {
        "type": "image_generation",
        "model": image_model,
        "output_format": "png",
    }
    assert mock_create_stream.call_args.kwargs["extra_headers"] == {
        "x-ms-oai-image-generation-deployment": image_deployment
    }
    image_data = mock_upload_media.call_args[0][1]
    assert image_data.file.getvalue() == b"A"
    assert image_data.content_type == "image/png"
    assert image_data.filename == "2025-06-14_155900_test_task.png"


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_image_requires_deployment(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test AI Task image generation is unavailable without a deployment."""
    with pytest.raises(
        HomeAssistantError,
        match=(
            "AI Task entity ai_task.azure_openai_ai_task "
            "does not support generating images"
        ),
    ):
        await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id=AI_TASK_ENTITY_ID,
            instructions="Generate test image",
        )
