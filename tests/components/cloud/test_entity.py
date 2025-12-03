"""Tests for helpers in the Home Assistant Cloud conversation entity."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
import pytest
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.cloud.const import AI_TASK_ENTITY_UNIQUE_ID, DOMAIN
from homeassistant.components.cloud.entity import (
    BaseCloudLLMEntity,
    _convert_content_to_param,
    _format_structured_output,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, llm, selector
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def cloud_entity(hass: HomeAssistant) -> BaseCloudLLMEntity:
    """Return a CloudLLMTaskEntity attached to hass."""
    cloud = MagicMock()
    cloud.llm = MagicMock()
    cloud.is_logged_in = True
    cloud.valid_subscription = True
    entry = MockConfigEntry(domain="cloud")
    entry.add_to_hass(hass)
    entity = BaseCloudLLMEntity(cloud, entry)
    entity.entity_id = "ai_task.cloud_ai_task"
    entity.hass = hass
    return entity


@pytest.fixture
def mock_prepare_files_for_prompt(
    cloud_entity: BaseCloudLLMEntity,
) -> AsyncMock:
    """Patch file preparation helper on the entity."""
    with patch.object(
        cloud_entity,
        "_async_prepare_files_for_prompt",
        AsyncMock(),
    ) as mock:
        yield mock


class DummyTool(llm.Tool):
    """Simple tool used for schema conversion tests."""

    name = "do_something"
    description = "Test tool"
    parameters = vol.Schema({vol.Required("value"): str})

    async def async_call(self, hass: HomeAssistant, tool_input, llm_context):
        """No-op implementation."""
        return {"value": "done"}


async def test_format_structured_output() -> None:
    """Test that structured output schemas are normalized."""
    schema = vol.Schema(
        {
            vol.Required("name"): selector.TextSelector(),
            vol.Optional("age"): selector.NumberSelector(
                config=selector.NumberSelectorConfig(min=0, max=120),
            ),
            vol.Required("stuff"): selector.ObjectSelector(
                {
                    "multiple": True,
                    "fields": {
                        "item_name": {"selector": {"text": None}},
                        "item_value": {"selector": {"text": None}},
                    },
                }
            ),
        }
    )

    assert _format_structured_output(schema, None) == {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "number", "minimum": 0.0, "maximum": 120.0},
            "stuff": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_name": {"type": "string"},
                        "item_value": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "required": ["name", "stuff"],
        "additionalProperties": False,
    }


async def test_prepare_files_for_prompt(
    cloud_entity: BaseCloudLLMEntity, tmp_path: Path
) -> None:
    """Test that media attachments are converted to the expected payload."""
    image_path = tmp_path / "doorbell.jpg"
    Image.new("RGB", (2, 2), "blue").save(image_path, "JPEG")
    pdf_path = tmp_path / "context.pdf"
    pdf_path.write_bytes(b"%PDF-1.3\nmock\n")

    attachments = [
        conversation.Attachment(
            media_content_id="media-source://media/doorbell.jpg",
            mime_type="image/jpeg",
            path=image_path,
        ),
        conversation.Attachment(
            media_content_id="media-source://media/context.pdf",
            mime_type="application/pdf",
            path=pdf_path,
        ),
    ]

    files = await cloud_entity._async_prepare_files_for_prompt(attachments)

    assert files[0] == {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64,"
        + base64.b64encode(image_path.read_bytes()).decode(),
        "detail": "auto",
    }
    assert files[1] == {
        "type": "input_file",
        "filename": "context.pdf",
        "file_data": "data:application/pdf;base64,"
        + base64.b64encode(pdf_path.read_bytes()).decode(),
    }


async def test_prepare_files_for_prompt_invalid_type(
    cloud_entity: BaseCloudLLMEntity, tmp_path: Path
) -> None:
    """Test that unsupported attachments raise an error."""
    text_path = tmp_path / "notes.txt"
    text_path.write_text("notes")

    attachments = [
        conversation.Attachment(
            media_content_id="media-source://media/notes.txt",
            mime_type="text/plain",
            path=text_path,
        )
    ]

    with pytest.raises(
        HomeAssistantError,
        match="Only images and PDF are currently supported as attachments",
    ):
        await cloud_entity._async_prepare_files_for_prompt(attachments)


async def test_prepare_chat_for_generation_appends_attachments(
    hass: HomeAssistant,
    cloud_entity: BaseCloudLLMEntity,
    mock_prepare_files_for_prompt: AsyncMock,
) -> None:
    """Test chat preparation adds LLM tools, attachments, and metadata."""
    chat_log = conversation.ChatLog(hass, "conversation-id")
    attachment = conversation.Attachment(
        media_content_id="media-source://media/doorbell.jpg",
        mime_type="image/jpeg",
        path=Path(hass.config.path("doorbell.jpg")),
    )
    chat_log.async_add_user_content(
        conversation.UserContent(content="Describe the door", attachments=[attachment])
    )
    chat_log.llm_api = MagicMock(
        tools=[DummyTool()],
        custom_serializer=None,
    )

    files = [{"type": "input_image", "image_url": "data://img", "detail": "auto"}]

    mock_prepare_files_for_prompt.return_value = files
    messages = _convert_content_to_param(chat_log.content)
    response = await cloud_entity._prepare_chat_for_generation(
        chat_log,
        messages,
        response_format={"type": "json"},
    )

    assert response["conversation_id"] == "conversation-id"
    assert response["response_format"] == {"type": "json"}
    assert response["tool_choice"] == "auto"
    assert len(response["tools"]) == 2
    assert response["tools"][0]["name"] == "do_something"
    assert response["tools"][1]["type"] == "web_search"
    assert response["messages"] is messages
    mock_prepare_files_for_prompt.assert_awaited_once_with([attachment])


async def test_prepare_chat_for_generation_passes_messages_through(
    hass: HomeAssistant, cloud_entity: BaseCloudLLMEntity
) -> None:
    """Test that prepared messages are forwarded unchanged."""
    chat_log = conversation.ChatLog(hass, "conversation-id")
    chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(agent_id="agent", content="Ready")
    )
    messages = _convert_content_to_param(chat_log.content)

    response = await cloud_entity._prepare_chat_for_generation(chat_log, messages)

    assert response["messages"] == messages
    assert response["conversation_id"] == "conversation-id"


async def test_async_handle_chat_log_service_sets_structured_output_non_strict(
    hass: HomeAssistant,
    cloud: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_cloud_login: None,
) -> None:
    """Ensure structured output requests always disable strict validation via service."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "ai_task", DOMAIN, AI_TASK_ENTITY_UNIQUE_ID
    )
    assert entity_id is not None

    async def _empty_stream():
        return

    async def _fake_delta_stream(
        self: conversation.ChatLog,
        agent_id: str,
        stream,
    ):
        content = conversation.AssistantContent(
            agent_id=agent_id, content='{"value": "ok"}'
        )
        self.async_add_assistant_content_without_tools(content)
        yield content

    cloud.llm.async_generate_data = AsyncMock(return_value=_empty_stream())

    with patch(
        "homeassistant.components.conversation.chat_log.ChatLog.async_add_delta_content_stream",
        _fake_delta_stream,
    ):
        await hass.services.async_call(
            "ai_task",
            "generate_data",
            {
                "entity_id": entity_id,
                "task_name": "Device Report",
                "instructions": "Provide value.",
                "structure": {
                    "value": {
                        "selector": {"text": None},
                        "required": True,
                    }
                },
            },
            blocking=True,
            return_response=True,
        )

    cloud.llm.async_generate_data.assert_awaited_once()
    _, kwargs = cloud.llm.async_generate_data.call_args

    assert kwargs["response_format"]["json_schema"]["strict"] is False
