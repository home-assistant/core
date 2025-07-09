"""Test AI Task platform of Google Generative AI Conversation integration."""

from unittest.mock import AsyncMock

from google.genai.types import GenerateContentResponse
import pytest
import voluptuous as vol

from homeassistant.components import ai_task
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

    assert len(mock_chat_create.mock_calls) == 2
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
