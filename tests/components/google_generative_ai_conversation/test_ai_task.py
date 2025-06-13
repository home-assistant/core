"""Test AI Task platform of Google Generative AI Conversation integration."""

from unittest.mock import AsyncMock

from google.genai.types import GenerateContentResponse
import pytest

from homeassistant.components import ai_task
from homeassistant.core import HomeAssistant

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
) -> None:
    """Test empty response."""
    entity_id = "ai_task.google_generative_ai_conversation"
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
    result = await ai_task.async_generate_text(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        task_type="summary",
        instructions="Test prompt",
    )
    assert result.result == "Hi there!"
