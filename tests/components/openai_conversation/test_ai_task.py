"""Test AI Task platform of OpenAI Conversation integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components import ai_task
from homeassistant.core import HomeAssistant

from .common import create_message_item

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_init_component")
async def test_ai_task_generate_text(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
) -> None:
    """Test that AI task can generate text."""
    entity_id = "ai_task.openai_ai_task"
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hi there!", output_index=0)
    ]

    result = await ai_task.async_generate_text(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        instructions="Test prompt",
    )
    assert result.text == "Hi there!"
