"""Test AI Task platform of Google Generative AI Conversation integration."""

from unittest.mock import AsyncMock

from google.genai.types import GenerateContentResponse
import pytest

from homeassistant.components import ai_task
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.conversation import (
    MockChatLog,
    mock_chat_log,  # noqa: F401
)


@pytest.mark.usefixtures("mock_init_component")
async def test_run_task(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test empty response."""
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
