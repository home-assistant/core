"""Test AI Task structured data generation."""

from unittest.mock import AsyncMock

from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import ai_task
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, selector

from . import setup_integration

from tests.common import MockConfigEntry


async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test AI Task structured data generation."""
    await setup_integration(hass, mock_config_entry)
    # Mock the OpenAI response stream with JSON data
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
        entity_id="ai_task.gemini_1_5_pro_none",
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
            "name": "weather",
            "schema": {
                "additionalProperties": False,
                "properties": {
                    # "characters": {
                    #     "description": "List of characters",
                    #     "items": {"type": "string"},
                    #     "type": "array",
                    # }
                    "conditions": {
                        "description": "Weather conditions description",
                        "type": "string",
                    },
                    "location": {
                        "description": "City or location name",
                        "type": "string",
                    },
                    "temperature": {
                        "description": "Temperature in Celsius",
                        "type": "number",
                    },
                },
                "required": [
                    # "characters",
                    "location",
                    "temperature",
                    "conditions",
                ],
                "type": "object",
            },
            "strict": True,
        },
        "type": "json_schema",
    }
